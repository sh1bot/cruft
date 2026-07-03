-- Pure, dependency-free parsing of a buffer name into a git revision spec.
--
-- This module contains ZERO references to `vim.*` so it can be unit-tested with
-- a stock Lua interpreter.  It answers a single question, syntactically and
-- without touching the filesystem or git:
--
--   "Does this name look enough like a git revision that we should try to
--    resolve it, and if so, what is the revision and (maybe) the path?"
--
-- The actual "does it exist in the repo" check happens later, in the git layer.
-- Here we only gate on shape, which is the cheap disambiguation the user asked
-- for: an unadorned token is treated as a revision only when it is a hex value
-- or contains one of the punctuation characters git uses in revisions.  A
-- trailing colon is the explicit "this is a revision, deduce the filename"
-- marker.

local M = {}

-- Characters that git uses in revision expressions but that essentially never
-- appear in an ordinary, about-to-be-created filename.  Presence of any of
-- these in an otherwise plain token is our signal that the user meant a
-- revision (e.g. `HEAD^`, `HEAD~3`, `@{u}`, `main@{yesterday}`).
--
-- The colon is handled separately (it is the path/deduce separator), and dots
-- and dashes are deliberately excluded because they are common in filenames.
local REV_PUNCT = "[%^~@{}]"

-- A token is treated as hex (i.e. a possible abbreviated/full object id) when it
-- is all hex digits and within a plausible length window.  `min_hex` guards
-- against short dictionary words that happen to be hex ("dead", "beef").
-- Default minimum length for a bare hex token to count as an object id.  Git's
-- own default abbreviation (core.abbrev) is 7, which is a good floor: it admits
-- realistic short ids while rejecting 4-letter hex words ("dead", "cafe").
local DEFAULT_MIN_HEX = 7

local function looks_hex(s, min_hex)
  min_hex = min_hex or DEFAULT_MIN_HEX
  return s:match("^%x+$") ~= nil and #s >= min_hex and #s <= 64
end
M.looks_hex = looks_hex

-- Reject buffer names that belong to a URL-like scheme (fugitive://, oil://,
-- term://, http://, ...).  Those are other plugins' virtual buffers and are
-- never a bare git revision.
local function is_uri(name)
  return name:match("^%w[%w+.%-]*://") ~= nil
end

--- Parse a buffer name into a revision spec.
--- @param name string        The name the user tried to open (as typed).
--- @param opts table|nil      { min_hex = number }
--- @return table|nil spec     nil when `name` is not revision-shaped, otherwise:
---   {
---     rev       = string,    -- the revision part (may be "" for the index)
---     path      = string?,   -- explicit path, or nil when it must be deduced
---     needs_path = boolean,  -- true when the filename has to be deduced
---     explicit  = boolean,   -- true when a colon made the intent unambiguous
---   }
function M.parse(name, opts)
  opts = opts or {}
  if type(name) ~= "string" or name == "" then
    return nil
  end
  if is_uri(name) then
    return nil
  end

  local colon = name:find(":", 1, true)
  if colon then
    local rev = name:sub(1, colon - 1)
    local path = name:sub(colon + 1)

    -- Guard against a Windows drive letter ("C:\foo", "C:/foo") being mistaken
    -- for `rev:path`.
    if #rev == 1 and rev:match("%a") and path:match("^[/\\]") then
      return nil
    end

    if path == "" then
      -- Trailing colon: the explicit "treat as revision, deduce filename" form.
      -- Requires a non-empty revision (a lone ":" is not meaningful here).
      if rev == "" then
        return nil
      end
      return { rev = rev, path = nil, needs_path = true, explicit = true }
    end

    -- `rev:path` (git's blob syntax).  `rev` may be empty, which is git's
    -- index/staging notation (":path" == ":0:path").
    return { rev = rev, path = path, needs_path = false, explicit = true }
  end

  -- No colon: only treat as a revision when it is hex, or carries a git
  -- revision punctuation character.  Plain alphanumeric tokens (HEAD, master,
  -- v1.2.3, README) are left alone so they behave as ordinary new files.
  if looks_hex(name, opts.min_hex) or name:match(REV_PUNCT) then
    return { rev = name, path = nil, needs_path = true, explicit = false }
  end

  return nil
end

return M
