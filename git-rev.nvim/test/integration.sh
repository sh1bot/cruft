#!/usr/bin/env bash
# End-to-end tests for gitrev.nvim against a throwaway git repository.
#
# Requires: nvim, git.  Run from anywhere:  test/integration.sh
set -u

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0
say() { printf '%s\n' "$*"; }
ok()   { pass=$((pass + 1)); say "  ok   - $1"; }
bad()  { fail=$((fail + 1)); say "  FAIL - $1"; }

# --- build a small repo with history -----------------------------------------
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
cd "$WORK"
git init -q -b main
mkdir -p src

# A large blob (> default 10MiB) and a binary blob.  Committed FIRST so that
# they do not sit between hello.c's two revisions -- that keeps HEAD^1 pointing
# at hello.c's v1 for the deduction tests below.
head -c 11000000 /dev/zero | tr '\0' 'x' > big.txt
printf 'ABC\0\0DEF binary\0here' > bin.dat
git add -A && git commit -qm extras

cat > src/hello.c <<'EOF'
#include <stdio.h>
int main(void) { puts("v1"); return 0; }
EOF
git add -A && git commit -qm v1
# second revision, so HEAD^1 differs from HEAD
cat > src/hello.c <<'EOF'
#include <stdio.h>
int main(void) { puts("v2"); return 0; }
EOF
git add -A && git commit -qm v2

MIN_INIT="$WORK/init.lua"
cat > "$MIN_INIT" <<EOF
vim.opt.runtimepath:prepend("$PLUGIN_ROOT")
vim.opt.swapfile = false
EOF

# run nvim headless, print a probe line, capture it
# usage: run_nvim <lua-after-load> -- <nvim args...>
run_nvim() {
  local lua="$1"; shift
  nvim --headless -u "$MIN_INIT" "$@" \
    +"lua $lua" +"qa!" 2>&1
}

# ---------------------------------------------------------------------------
# 1. diff-on-the-commandline: nvim -d src/hello.c HEAD^1  (deduced filename)
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD^1"); io.write("RO="..tostring(vim.bo[b].readonly)..";FT="..vim.bo[b].filetype..";BT="..vim.bo[b].buftype..";TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  -d src/hello.c 'HEAD^1')"
case "$out" in
  *"RO=true"*"FT=c"*"BT=nofile"*'puts("v1")'*) ok "nvim -d deduces filename, v1 content, RO, ft=c" ;;
  *) bad "nvim -d HEAD^1 :: $out" ;;
esac

# 2. :diffsplit HEAD^1 from an open file (deduce from issuing buffer)
out="$(cd "$WORK" && run_nvim \
  'vim.cmd("diffsplit HEAD^1"); local b=vim.fn.bufnr("HEAD^1"); io.write("RO="..tostring(vim.bo[b].readonly)..";TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  src/hello.c)"
case "$out" in
  *"RO=true"*'puts("v1")'*) ok ":diffsplit HEAD^1 deduces from current buffer" ;;
  *) bad ":diffsplit HEAD^1 :: $out" ;;
esac

# 3. explicit rev:path form
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:src/hello.c"); io.write("TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  'HEAD:src/hello.c')"
case "$out" in
  *'puts("v2")'*) ok "explicit HEAD:src/hello.c loads current version" ;;
  *) bad "HEAD:src/hello.c :: $out" ;;
esac

# 4. trailing-colon explicit deduce form
out="$(cd "$WORK" && run_nvim \
  'vim.cmd("diffsplit HEAD^1:"); local b=vim.fn.bufnr("HEAD^1:"); io.write("TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n").."|BT="..vim.bo[b].buftype)' \
  src/hello.c)"
case "$out" in
  *'puts("v1")'*"BT=nofile"*) ok "trailing-colon HEAD^1: deduces filename" ;;
  *) bad "HEAD^1: :: $out" ;;
esac

# 5. plain non-revision filename must be a normal (writable, empty) new file
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("notes.txt"); io.write("MOD="..tostring(vim.bo[b].modifiable)..";BT="..vim.bo[b].buftype..";N="..#vim.api.nvim_buf_get_lines(b,0,-1,false))' \
  'notes.txt')"
case "$out" in
  *"MOD=true"*"BT="*";N=1"*) ok "plain notes.txt stays a normal new file" ;;
  *) bad "notes.txt :: $out" ;;
esac

# 6. bare 'HEAD' (no punctuation, not hex) must NOT be hijacked
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD"); io.write("MOD="..tostring(vim.bo[b].modifiable)..";N="..#vim.api.nvim_buf_get_lines(b,0,-1,false))' \
  'HEAD')"
case "$out" in
  *"MOD=true"*";N=1"*) ok "bare HEAD is left as an ordinary new file" ;;
  *) bad "bare HEAD :: $out" ;;
esac

# 7. revision that does not resolve -> fall through to new file
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD~99"); io.write("MOD="..tostring(vim.bo[b].modifiable))' \
  src/hello.c 'HEAD~99')"
case "$out" in
  *"MOD=true"*) ok "unresolvable HEAD~99 falls through to a new file" ;;
  *) bad "HEAD~99 :: $out" ;;
esac

# 8. large blob guard: HEAD:big.txt should be skipped (left modifiable/empty)
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:big.txt"); io.write("MOD="..tostring(vim.bo[b].modifiable)..";N="..#vim.api.nvim_buf_get_lines(b,0,-1,false))' \
  'HEAD:big.txt' 2>/dev/null)"
case "$out" in
  *"MOD=true"*";N=1"*) ok "large blob is guarded (not loaded)" ;;
  *) bad "large blob guard :: $out" ;;
esac

# 9. binary blob guard: HEAD:bin.dat should be skipped
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:bin.dat"); io.write("MOD="..tostring(vim.bo[b].modifiable)..";N="..#vim.api.nvim_buf_get_lines(b,0,-1,false))' \
  'HEAD:bin.dat' 2>/dev/null)"
case "$out" in
  *"MOD=true"*";N=1"*) ok "binary blob is guarded (not loaded)" ;;
  *) bad "binary blob guard :: $out" ;;
esac

# 10. outside any git repo -> fall through
NOGIT="$(mktemp -d)"
out="$(cd "$NOGIT" && run_nvim \
  'local b=vim.fn.bufnr("HEAD^1"); io.write("MOD="..tostring(vim.bo[b].modifiable))' \
  somefile.txt 'HEAD^1')"
rm -rf "$NOGIT"
case "$out" in
  *"MOD=true"*) ok "outside a git repo falls through" ;;
  *) bad "outside repo :: $out" ;;
esac

# 11. loose subdir: cwd inside src/, non-qualified path HEAD:hello.c resolves
out="$(cd "$WORK/src" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:hello.c"); io.write("OBJ="..tostring(vim.b[b].gitrev_object)..";TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  'HEAD:hello.c')"
case "$out" in
  *'puts("v2")'*) ok "loose: HEAD:hello.c resolves from subdirectory" ;;
  *) bad "subdir HEAD:hello.c :: $out" ;;
esac

# 12. regression: fully-qualified path from repo root still resolves
out="$(cd "$WORK" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:src/hello.c"); io.write("TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  'HEAD:src/hello.c')"
case "$out" in
  *'puts("v2")'*) ok "root-relative HEAD:src/hello.c still resolves from repo root" ;;
  *) bad "root-relative regression :: $out" ;;
esac

# 13. loose subdir with an explicit subpath: from src/, HEAD:hello.c vs a
#     deeper tree -- ensure a nested cwd-relative path resolves too.
mkdir -p "$WORK/src/deep" && (cd "$WORK" && cat > src/deep/z.txt <<< 'zebra' && git add -A && git commit -qm z >/dev/null)
out="$(cd "$WORK/src" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:deep/z.txt"); io.write("TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  'HEAD:deep/z.txt')"
case "$out" in
  *'zebra'*) ok "loose: HEAD:deep/z.txt resolves relative to subdirectory cwd" ;;
  *) bad "subdir nested path :: $out" ;;
esac

# 14. explicit rev:path issued from OUTSIDE any repo: the repo must be
#     discovered from the file's own location, not from cwd.
OUTER="$(mktemp -d)"            # not a git repo
mkdir -p "$OUTER/proj/sub"
( cd "$OUTER/proj" && git init -q -b main \
    && printf 'from-HEAD\n' > sub/f.txt && git add -A && git commit -qm one >/dev/null \
    && printf 'working\n' > sub/f.txt )   # working tree differs from HEAD
out="$(cd "$OUTER" && run_nvim \
  'local b=vim.fn.bufnr("HEAD:proj/sub/f.txt"); io.write("OBJ="..tostring(vim.b[b].gitrev_object)..";RO="..tostring(vim.bo[b].readonly)..";TXT="..table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\n"))' \
  'HEAD:proj/sub/f.txt')"
rm -rf "$OUTER"
case "$out" in
  *"RO=true"*'from-HEAD'*) ok "explicit rev:path discovers repo from file location, not cwd" ;;
  *) bad "explicit rev:path from outside repo :: $out" ;;
esac

say ""
say "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
