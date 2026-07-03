-- Plain-Lua unit tests for the revision parser.
-- Run with:  lua test/revspec_spec.lua   (from the plugin root)

package.path = "./lua/?.lua;./lua/?/init.lua;" .. package.path
local revspec = require("gitrev.revspec")

local failures = 0
local count = 0

local function check(name, ok, msg)
  count = count + 1
  if not ok then
    failures = failures + 1
    print(string.format("  FAIL: %s -- %s", name, msg or ""))
  end
end

local function eq(a, b)
  return a == b
end

-- Helper: assert `name` is NOT considered a revision.
local function refute_rev(name)
  local spec = revspec.parse(name)
  check(name, spec == nil, "expected nil, got " .. tostring(spec and vim_inspect(spec)))
end

-- Minimal inspect so failures are readable without vim.
function vim_inspect(t)
  if type(t) ~= "table" then return tostring(t) end
  local parts = {}
  for k, v in pairs(t) do parts[#parts + 1] = tostring(k) .. "=" .. tostring(v) end
  return "{" .. table.concat(parts, ", ") .. "}"
end

local function expect(name, want)
  local spec = revspec.parse(name)
  if want == nil then
    check(name, spec == nil, "expected nil, got " .. vim_inspect(spec))
    return
  end
  if spec == nil then
    check(name, false, "expected a spec, got nil")
    return
  end
  local ok = eq(spec.rev, want.rev)
    and eq(spec.path, want.path)
    and eq(spec.needs_path, want.needs_path)
    and eq(spec.explicit, want.explicit)
  check(name, ok, "got " .. vim_inspect(spec) .. " want " .. vim_inspect(want))
end

print("revspec.parse")

-- Bare revisions with git punctuation -> deduce filename.
expect("HEAD^1", { rev = "HEAD^1", path = nil, needs_path = true, explicit = false })
expect("HEAD~3", { rev = "HEAD~3", path = nil, needs_path = true, explicit = false })
expect("@{u}", { rev = "@{u}", path = nil, needs_path = true, explicit = false })
expect("main@{yesterday}", { rev = "main@{yesterday}", path = nil, needs_path = true, explicit = false })
expect("HEAD^{}", { rev = "HEAD^{}", path = nil, needs_path = true, explicit = false })

-- Hex object ids (no punctuation) -> deduce filename.
expect("deadbeef", { rev = "deadbeef", path = nil, needs_path = true, explicit = false })
expect("a1b2c3d", { rev = "a1b2c3d", path = nil, needs_path = true, explicit = false })

-- Trailing colon: explicit "revision, deduce filename".
expect("HEAD:", { rev = "HEAD", path = nil, needs_path = true, explicit = true })
expect("HEAD^1:", { rev = "HEAD^1", path = nil, needs_path = true, explicit = true })
expect("v1.2.3:", { rev = "v1.2.3", path = nil, needs_path = true, explicit = true })

-- Explicit rev:path (git blob syntax).
expect("HEAD:src/main.c", { rev = "HEAD", path = "src/main.c", needs_path = false, explicit = true })
expect("HEAD^1:Makefile", { rev = "HEAD^1", path = "Makefile", needs_path = false, explicit = true })
expect("abc123:a/b.txt", { rev = "abc123", path = "a/b.txt", needs_path = false, explicit = true })
-- Index (staging) form: empty rev.
expect(":staged.txt", { rev = "", path = "staged.txt", needs_path = false, explicit = true })

-- Plain names that must NOT be hijacked (no punctuation, not hex).
refute_rev("HEAD")            -- deliberately excluded; use "HEAD:" to force it
refute_rev("master")
refute_rev("README")
refute_rev("v1.2.3")          -- dots are not a revision signal
refute_rev("my-notes")        -- dashes are not a revision signal
refute_rev("notes.txt")
refute_rev("Makefile")
refute_rev("dead")            -- hex but shorter than min length
refute_rev("")

-- URL-like virtual buffers from other plugins are left alone.
refute_rev("fugitive:///repo/.git//0/foo")
refute_rev("oil:///home/user/")
refute_rev("term://zsh")
refute_rev("http://example.com/x")

-- Windows drive letters are not rev:path.
refute_rev("C:/Users/me/file.txt")
refute_rev("D:\\work\\a.c")

-- min_hex is configurable.
do
  local spec = revspec.parse("dead", { min_hex = 4 })
  check("dead@min_hex=4", spec ~= nil and spec.rev == "dead", "expected dead to parse at min_hex=4")
end

print(string.format("\n%d checks, %d failures", count, failures))
os.exit(failures == 0 and 0 or 1)
