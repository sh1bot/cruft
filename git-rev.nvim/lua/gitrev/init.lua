-- gitrev: in-fill buffers whose name looks like a git revision.
--
-- When Neovim is asked to edit a file that does not exist, we inspect the name.
-- If it parses as a git revision (see gitrev/revspec.lua) and resolves to a
-- blob in the repository, we load that blob's content into the buffer, mark it
-- read-only, and give it the filetype of the file it stands in for.
--
-- Design constraints (from the request):
--   * Cheap disambiguation first, git second.  We never shell out for a name
--     that is not revision-shaped.
--   * Minimal external calls.  A successful in-fill costs two git invocations
--     (one metadata probe, one blob read); a miss costs at most one.
--   * No stalls.  Every git call is bounded by a timeout and cannot hang the
--     editor, even on Neovim 0.9 which lacks `vim.system`.
--   * Guard against large and binary blobs.

local revspec = require("gitrev.revspec")

local M = {}

M.config = {
  enabled = true,
  -- Maximum blob size to load, in bytes.  Larger blobs are skipped with a
  -- warning and the buffer falls through to normal new-file behaviour.
  max_size = 10 * 1024 * 1024,
  -- Hard ceiling on how long any single git call may run, in milliseconds.
  timeout = 2000,
  -- Minimum length for a bare hex token to be treated as an object id.
  min_hex = 7,
  -- Emit notifications for guard trips (too large / binary).
  notify = true,
}

function M.setup(opts)
  M.config = vim.tbl_deep_extend("force", M.config, opts or {})
end

local function warn(msg)
  if M.config.notify then
    vim.notify("[gitrev] " .. msg, vim.log.levels.WARN)
  end
end

-- Run a command with a hard timeout, without a shell (list form).  Works on
-- Neovim 0.9+ by driving jobstart with vim.wait, so a slow/hung git can never
-- block the editor for longer than `timeout` ms.
--
-- Returns: { code = number, stdout = string, timed_out = boolean }
-- `stdout` is the raw joined output; suitable for the plain-text probes here.
local function run(cmd, opts)
  opts = opts or {}
  local chunks = {}
  local exit_code, done = nil, false

  local ok, job = pcall(vim.fn.jobstart, cmd, {
    stdout_buffered = true,
    on_stdout = function(_, data)
      if data then
        -- jobstart splits on newlines; rejoin to recover the stream.
        chunks[#chunks + 1] = table.concat(data, "\n")
      end
    end,
    on_exit = function(_, code)
      exit_code = code
      done = true
    end,
    env = { GIT_TERMINAL_PROMPT = "0", GIT_OPTIONAL_LOCKS = "0" },
  })
  if not ok or job <= 0 then
    return { code = -1, stdout = "", timed_out = false }
  end

  if opts.stdin then
    pcall(vim.fn.chansend, job, opts.stdin)
    pcall(vim.fn.chanclose, job, "stdin")
  end

  local finished = vim.wait(opts.timeout or M.config.timeout, function()
    return done
  end, 10)
  if not finished then
    pcall(vim.fn.jobstop, job)
    return { code = -1, stdout = table.concat(chunks, ""), timed_out = true }
  end
  return { code = exit_code, stdout = table.concat(chunks, ""), timed_out = false }
end

-- Probe an object with a single `git cat-file --batch-check` call.  Returns the
-- resolved oid, type and size, or nil when the object does not exist / the
-- directory is not a git repository / git timed out.
local function probe(dir, object)
  local res = run({ "git", "-C", dir, "cat-file", "--batch-check" }, {
    stdin = object .. "\n",
  })
  if res.timed_out or res.code ~= 0 then
    return nil
  end
  local line = vim.trim(res.stdout)
  -- "<oid> <type> <size>" on success, "<object> missing" otherwise.
  local oid, otype, size = line:match("^(%x+)%s+(%S+)%s+(%d+)$")
  if not oid then
    return nil
  end
  return { oid = oid, type = otype, size = tonumber(size) }
end

-- Read a blob by oid into a Lua string, preserving bytes exactly (including
-- NULs) by routing through a temp file rather than a captured channel.  The oid
-- is pure hex, so shell interpolation is safe here.
local function read_blob(dir, oid)
  local tmp = vim.fn.tempname()
  local shell = string.format(
    "git -C %s cat-file blob %s > %s",
    vim.fn.shellescape(dir),
    oid,
    vim.fn.shellescape(tmp)
  )
  local res = run({ "sh", "-c", shell })
  if res.timed_out or res.code ~= 0 then
    pcall(vim.fn.delete, tmp)
    return nil
  end
  local f = io.open(tmp, "rb")
  if not f then
    pcall(vim.fn.delete, tmp)
    return nil
  end
  local data = f:read("*a")
  f:close()
  pcall(vim.fn.delete, tmp)
  return data
end

local function is_readable_file(p)
  return p ~= nil and p ~= "" and vim.fn.filereadable(p) == 1
end

-- Collect real, existing files that could lend their name to a bare revision,
-- in priority order: alternate file, other windows in this tab, the argument
-- list, then any other loaded buffer.  This covers both `:diffsplit HEAD^1`
-- (deduce from the buffer that issued the command) and `nvim -d file.txt HEAD^1`
-- (deduce from the other file on the command line).
local function deduce_files(cur_buf, cur_names)
  local out, seen = {}, {}
  local skip = {}
  for _, n in ipairs(cur_names) do
    if n and n ~= "" then
      skip[vim.fn.fnamemodify(n, ":p")] = true
    end
  end
  local function add(p)
    if not p or p == "" then
      return
    end
    local full = vim.fn.fnamemodify(p, ":p")
    if seen[full] or skip[full] then
      return
    end
    seen[full] = true
    if is_readable_file(full) then
      out[#out + 1] = full
    end
  end

  add(vim.fn.expand("#"))
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local b = vim.api.nvim_win_get_buf(win)
    if b ~= cur_buf then
      add(vim.api.nvim_buf_get_name(b))
    end
  end
  local ok, argv = pcall(vim.fn.argv)
  if ok and type(argv) == "table" then
    for _, a in ipairs(argv) do
      add(a)
    end
  end
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if b ~= cur_buf and vim.api.nvim_buf_is_loaded(b) then
      add(vim.api.nvim_buf_get_name(b))
    end
  end
  return out
end

local function is_anchored(p)
  return p:sub(1, 1) == "/" or p:sub(1, 2) == "./" or p:sub(1, 3) == "../"
end

-- Address a real filesystem path as a git object relative to its own
-- directory.  Returns { dir, object } where `dir` is the file's directory (so
-- git discovers the repo that *contains the file*, not the one at cwd) and
-- `object` is `rev:./<basename>`.
local function object_for_file(rev, filepath)
  local abs = vim.fn.fnamemodify(filepath, ":p")
  return {
    dir = vim.fn.fnamemodify(abs, ":h"),
    object = rev .. ":./" .. vim.fn.fnamemodify(abs, ":t"),
  }
end

-- Work out an ordered list of { dir, object } candidates for a spec, or nil if
-- we cannot.  Each candidate is probed in turn until one resolves to a blob.
--   * explicit path form (rev:path): git's native `rev:path` is resolved
--     relative to the *repo root* of git's working directory, which is
--     surprising -- if cwd is not in a repo it fails even when the file plainly
--     lives in one.  So we treat the path as an ordinary (cwd-relative)
--     filename, resolve it to an absolute path, and let git discover the repo
--     that contains that file.  We then fall back to git's repo-root-relative
--     reading from cwd, so a path typed relative to the repo root from a
--     subdirectory keeps working too.
--   * deduced form (bare rev / trailing colon): borrow a filename from a real
--     file on the command line / in a sibling window and address it the same
--     way, relative to that file's own directory.
local function locate(spec, cur_buf, cur_names)
  if not spec.needs_path then
    local cwd = vim.fn.getcwd()
    local p = spec.path
    -- (1) cwd-relative filename; repo discovered from the file's own location.
    local cands = { object_for_file(spec.rev, p) }
    -- (2) git-native repo-root-relative from cwd (only meaningful when cwd is
    --     itself inside a repo).  Skip for already-anchored paths.
    if not is_anchored(p) then
      cands[#cands + 1] = { dir = cwd, object = spec.rev .. ":" .. p }
    end
    return cands, p
  end

  local files = deduce_files(cur_buf, cur_names)
  if #files == 0 then
    return nil
  end
  local file = files[1]
  local cand = object_for_file(spec.rev, file)
  return { cand }, vim.fn.fnamemodify(file, ":t")
end

-- Turn raw blob bytes into buffer lines, or nil if it looks binary.
local function to_lines(data)
  -- Binary guard: a NUL in the first chunk is the classic "this is not text"
  -- signal and is what git itself uses.
  if data:sub(1, 8192):find("\0", 1, true) then
    return nil
  end
  local had_trailing_nl = data:sub(-1) == "\n"
  local lines = vim.split(data, "\n", { plain = true })
  if had_trailing_nl then
    -- Drop the empty element produced by a trailing newline so we do not add a
    -- spurious blank final line.
    table.remove(lines)
  end
  return lines
end

-- The core: given a buffer and the name(s) it was opened under, try to in-fill.
-- Returns true when the buffer was taken over, false to fall through to
-- Neovim's default new-file behaviour.
function M.try_infill(buf, cur_names)
  if not M.config.enabled then
    return false
  end
  if not vim.api.nvim_buf_is_valid(buf) then
    return false
  end
  -- Only touch ordinary file buffers.
  if vim.bo[buf].buftype ~= "" then
    return false
  end

  local spec
  for _, name in ipairs(cur_names) do
    spec = revspec.parse(name, { min_hex = M.config.min_hex })
    if spec then
      break
    end
  end
  if not spec then
    return false
  end

  local candidates, display_path = locate(spec, buf, cur_names)
  if not candidates then
    return false
  end

  -- Metadata probe: existence + type + size (also fails fast when the candidate
  -- directory is not inside a git repository).  We try each candidate in turn
  -- and keep the first that names a blob.  In the common case this is a single
  -- git call; a fallback interpretation may cost one extra probe.
  local info, object, dir
  local tried = {}
  for _, c in ipairs(candidates) do
    local key = c.dir .. "\0" .. c.object
    if not tried[key] then
      tried[key] = true
      local i = probe(c.dir, c.object)
      if i and i.type == "blob" then
        info, object, dir = i, c.object, c.dir
        break
      end
    end
  end
  if not info then
    return false
  end
  if info.size > M.config.max_size then
    warn(string.format("%s is %d bytes (max %d); leaving as a new file",
      object, info.size, M.config.max_size))
    return false
  end

  local data = read_blob(dir, info.oid)
  if data == nil then
    return false
  end

  local lines = to_lines(data)
  if lines == nil then
    warn(object .. " looks binary; leaving as a new file")
    return false
  end

  -- Populate and lock down the buffer.
  vim.bo[buf].modifiable = true
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.bo[buf].modified = false
  vim.bo[buf].modifiable = false
  vim.bo[buf].readonly = true
  vim.bo[buf].swapfile = false
  -- nofile keeps the read-only history from being accidentally written back to
  -- a file literally named e.g. "HEAD^1".
  vim.bo[buf].buftype = "nofile"

  -- Inherit the filetype of the file we stood in for, so syntax highlighting
  -- and filetype-driven settings match the real file.
  local ft = vim.filetype.match({ filename = display_path, contents = lines })
  if ft and ft ~= "" then
    vim.bo[buf].filetype = ft
  end

  -- Leave a breadcrumb other tooling (e.g. a statusline) can pick up.
  vim.b[buf].gitrev_object = object

  return true
end

-- Autocmd entry point.  `file` is the name as typed (from <afile>); we also
-- consider the possibly-absolutised buffer name so a name like "HEAD^1" that
-- Neovim expanded to "/cwd/HEAD^1" is still recognised.
function M.on_new_file(buf, file)
  local names = {}
  local function push(n)
    if n and n ~= "" then
      for _, existing in ipairs(names) do
        if existing == n then
          return
        end
      end
      names[#names + 1] = n
    end
  end
  push(file)
  -- Absolutised buffer name, made relative to cwd, to recover the typed token.
  local bufname = vim.api.nvim_buf_get_name(buf)
  if bufname ~= "" then
    push(vim.fn.fnamemodify(bufname, ":."))
    push(bufname)
  end

  local ok, took = pcall(M.try_infill, buf, names)
  if not ok then
    -- Never let an error here break opening a file.
    return
  end
  return took
end

return M
