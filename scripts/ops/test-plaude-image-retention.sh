#!/usr/bin/env bash
# Mock docker exercises plaude-image-retention. No host docker and no QNAP.
set -euo pipefail
export LC_ALL=C

SCRIPT=$(cd -- "$(dirname "$0")" && pwd)/plaude-image-retention
TMP=
OUT=
ERR=
FIX=
BIN=
QNAP=
LOCAL=
ROOT=
MOCK_LOG=
IONICE_LOG=
STATUS=0

cleanup_test() {
  if [ -n "${TMP:-}" ] && [ -d "$TMP" ]; then
    chmod -R u+rwx "$TMP" 2>/dev/null || true
    rm -r -- "$TMP" || true
  fi
}
trap cleanup_test EXIT

fail() {
  printf '%s\n' "FAIL: $*" >&2
  printf '%s\n' '--- stdout ---' >&2
  cat "$OUT" >&2 || true
  printf '%s\n' '--- stderr ---' >&2
  cat "$ERR" >&2 || true
  printf '%s\n' '--- docker log ---' >&2
  cat "$MOCK_LOG" >&2 || true
  printf '%s\n' '--- ionice log ---' >&2
  cat "$IONICE_LOG" >&2 || true
  exit 1
}

need() {
  grep -q -F -- "$1" "$OUT" || fail "stdout missing: $1"
}

forbid() {
  if grep -q -F -- "$1" "$OUT"; then
    fail "stdout unexpectedly contains: $1"
  fi
}

want_status() {
  [ "$STATUS" -eq "$1" ] || fail "status $STATUS want $1"
}

hid() {
  printf 'sha256:%064d' "$1"
}

setup() {
  if [ -n "${TMP:-}" ] && [ -d "$TMP" ]; then
    chmod -R u+rwx "$TMP" 2>/dev/null || true
    rm -r -- "$TMP"
  fi
  unset PLAUDE_SHA256SUM SAVE_BYTES || true
  TMP=$(mktemp -d)
  OUT=$TMP/stdout
  ERR=$TMP/stderr
  FIX=$TMP/fix
  BIN=$TMP/bin
  QNAP=$TMP/qnap
  LOCAL=$TMP/local
  ROOT=$TMP/plaude
  MOCK_LOG=$TMP/docker.log
  IONICE_LOG=$TMP/ionice.log
  mkdir -p -- "$FIX" "$BIN" "$QNAP" "$LOCAL" "$ROOT"
  printf 'FROM scratch\n# plaude-test\n' > "$ROOT/Dockerfile"
  : > "$FIX/images.tsv"
  : > "$MOCK_LOG"
  : > "$IONICE_LOG"
  cat > "$BIN/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${MOCK_LOG:?}"
  for a in "$@"; do
    case "$a" in
      prune|-f|--force|--force=*)
        printf 'forbidden arg %s\n' "$a" >&2
        exit 97
        ;;
    esac
  done

  image_ls() {
  local ref="" dangling="" label=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --no-trunc) shift ;;
      --format) shift 2 ;;
      --filter)
        case "$2" in
          reference=*) ref=${2#reference=} ;;
          dangling=*) dangling=${2#dangling=} ;;
          label=*) label=${2#label=} ;;
          *) printf 'bad filter %s\n' "$2" >&2; exit 96 ;;
        esac
        shift 2
        ;;
      *) printf 'bad ls arg %s\n' "$1" >&2; exit 96 ;;
    esac
  done
  if [ "$ref" = plaude-web ] && [ -z "$dangling" ] && [ -z "$label" ]; then
    awk -F '\t' '$7=="repo" {print $1}' "$FIX/images.tsv"
    return 0
  fi
  if [ "$dangling" = true ] && [ "$label" = "com.docker.compose.project=plaude" ] && [ -z "$ref" ]; then
    awk -F '\t' '$7=="dangling" && $5=="plaude" {print $1}' "$FIX/images.tsv"
    return 0
  fi
  printf 'unexpected image ls ref=%s dangling=%s label=%s\n' "$ref" "$dangling" "$label" >&2
  exit 96
}

image_inspect() {
  local id=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --format) shift 2 ;;
      sha256:*) id=$1; shift ;;
      *) printf 'bad inspect arg %s\n' "$1" >&2; exit 96 ;;
    esac
  done
  [ -n "$id" ] || exit 96
  awk -F '\t' -v id="$id" '$1==id {printf "%s|%s|%s|%s|%s\n",$1,$2,$3,$4,$5; found=1} END {exit found?0:1}' "$FIX/images.tsv"
}

image_rm() {
  [ "$#" -eq 1 ] || { printf 'rm argc %s\n' "$#" >&2; exit 96; }
  case "$1" in
    sha256:*) ;;
    *) printf 'bad rm id %s\n' "$1" >&2; exit 96 ;;
  esac
  printf '%s\n' "$1" >> "$FIX/removed"
  if [ -f "$FIX/fail-rm" ] && grep -q -x -F -- "$1" "$FIX/fail-rm"; then
    printf 'mock rm failed\n' >&2
    exit 1
  fi
}

ps_cmd() {
  local saw_a=0 ancestor=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -a) saw_a=1; shift ;;
      --format) shift 2 ;;
      --filter)
        case "$2" in
          ancestor=*) ancestor=${2#ancestor=} ;;
          *) printf 'bad ps filter %s\n' "$2" >&2; exit 96 ;;
        esac
        shift 2
        ;;
      *) printf 'bad ps arg %s\n' "$1" >&2; exit 96 ;;
    esac
  done
  [ "$saw_a" -eq 1 ] || { printf 'ps without -a\n' >&2; exit 96; }
  [ -n "$ancestor" ] || { printf 'ps without ancestor\n' >&2; exit 96; }
  awk -F '\t' -v a="$ancestor" '$6=="yes" && ($1==a || substr($1,8)==a) {print "c" substr($1,8,12)}' "$FIX/images.tsv"
}

save_cmd() {
  [ "$#" -eq 1 ] || { printf 'save argc %s\n' "$#" >&2; exit 96; }
  printf '%s\n' "$1" >> "$FIX/saved"
  if [ -f "$FIX/save-fail" ]; then
    printf 'mock save failed\n' >&2
    exit 1
  fi
  dd if=/dev/zero bs="${SAVE_BYTES:-2048}" count=1 status=none
}

cmd=${1:-}
shift || true
case "$cmd" in
  image)
    sub=${1:-}
    shift || true
    case "$sub" in
      ls) image_ls "$@" ;;
      inspect) image_inspect "$@" ;;
      rm) image_rm "$@" ;;
      *) printf 'bad image sub %s\n' "$sub" >&2; exit 96 ;;
    esac
    ;;
  ps) ps_cmd "$@" ;;
  save) save_cmd "$@" ;;
  system|builder|stop|kill|compose)
    printf 'forbidden command %s\n' "$cmd" >&2
    exit 97
    ;;
  *)
    printf 'unexpected docker command %s\n' "$cmd" >&2
    exit 96
    ;;
esac
EOF
  cat > "$BIN/ionice" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${IONICE_LOG:?}"
[ "${1:-}" = "-c3" ] || { printf 'ionice not idle: %s\n' "$*" >&2; exit 95; }
shift
exec "$@"
EOF
  chmod +x "$BIN/docker" "$BIN/ionice"
  export FIX MOCK_LOG IONICE_LOG
}

add_image() {
  # id created size tags label in_use bucket
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$FIX/images.tsv"
}

load_standard_images() {
  ID111=$(hid 111)
  ID222=$(hid 222)
  ID333=$(hid 333)
  ID444=$(hid 444)
  ID555=$(hid 555)
  ID666=$(hid 666)
  ID777=$(hid 777)
  ID888=$(hid 888)
  : > "$FIX/images.tsv"
  add_image "$ID111" "2026-09-01T00:00:00Z" 1000 \
    "plaude-web:latest,plaude-web:pre-run111-20260901" plaude yes repo
  add_image "$ID222" "2026-10-15T00:00:00Z" 2000 \
    "plaude-web:pre-mid222-20261015" "" no repo
  add_image "$ID333" "2026-10-30T01:00:00Z" 3000 \
    "plaude-web:pre-new333-20261030" "" no repo
  add_image "$ID888" "2026-10-30T23:00:00Z" 8000 \
    "plaude-web:pre-aaa888-20261030" "" no repo
  add_image "$ID444" "2026-10-01T00:00:00Z" 4000 "" plaude no dangling
  add_image "$ID555" "2026-10-02T00:00:00Z" 5000 "" plaude yes dangling
  add_image "$ID666" "2026-10-31T00:00:00Z" 6000 \
    "plaude-web:pre-mix666-20261031,other-product:kept" "" no repo
  add_image "$ID777" "2026-10-31T00:00:00Z" 7000 "other-product:latest" "" no hidden
}

run() {
  set +e
  PLAUDE_QNAP_TRUST=1 \
    PLAUDE_DOCKER="$BIN/docker" \
    PLAUDE_IONICE="$BIN/ionice" \
    "$SCRIPT" --qnap-root "$QNAP" --local-tar-dir "$LOCAL" --plaude-root "$ROOT" \
    "$@" >"$OUT" 2>"$ERR"
  STATUS=$?
  set -e
}

run_untrusted() {
  set +e
  env -u PLAUDE_QNAP_TRUST \
    PLAUDE_DOCKER="$BIN/docker" \
    PLAUDE_IONICE="$BIN/ionice" \
    "$SCRIPT" --qnap-root "$QNAP" --local-tar-dir "$LOCAL" --plaude-root "$ROOT" \
    "$@" >"$OUT" 2>"$ERR"
  STATUS=$?
  set -e
}

make_set() {
  local id=$1 day=$2 nbytes=$3 dir
  dir="$QNAP/$id/$day"
  mkdir -p -- "$dir/source"
  head -c "$nbytes" </dev/zero > "$dir/plaude-web.tar"
  ( cd "$dir" && sha256sum plaude-web.tar > plaude-web.tar.sha256 )
  printf 'FROM scratch\n' > "$dir/source/Dockerfile"
}

measured() {
  find -P "$1" -type f -exec stat -c '%s' {} + | awk '{s+=$1} END {print s+0}'
}

assert_ps_and_ls() {
  local line
  grep -q -F -- 'reference=plaude-web' "$MOCK_LOG" || fail "missing plaude-web image ls"
  grep -q -F -- 'dangling=true' "$MOCK_LOG" || fail "missing dangling image ls"
  grep -q -F -- 'label=com.docker.compose.project=plaude' "$MOCK_LOG" || fail "missing compose label filter"
  while IFS= read -r line; do
    case "$line" in
      "ps "*)
        case "$line" in
          *" -a "*|ps\ -a*) ;;
          *) fail "ps without -a: $line" ;;
        esac
        case "$line" in
          *ancestor=*) ;;
          *) fail "ps without ancestor=: $line" ;;
        esac
        ;;
    esac
  done < "$MOCK_LOG"
}

test_help_and_flags() {
  setup
  run --help
  want_status 0
  need "usage: plaude-image-retention"
  run --apply --dry-run
  want_status 1
  grep -q -F -- 'pass only one' "$ERR" || fail "missing both-flags error"
  run --nope
  want_status 1
  printf 'ok help and flags\n'
}

test_refuses_unsafe_local_dirs() {
  setup
  mkdir -p -- "$ROOT/data"
  run --apply --local-tar-dir "$ROOT/data/newdir"
  want_status 1
  grep -q -F -- 'meeting data' "$ERR" || fail "missing data-dir error"
  [ ! -d "$ROOT/data/newdir" ] || fail "created a directory inside meeting data"
  run --apply --local-tar-dir "$QNAP/scratch"
  want_status 1
  grep -q -F -- 'not on QNAP' "$ERR" || fail "missing qnap local-dir error"
  [ ! -e "$QNAP/scratch" ] || fail "created local tar dir on qnap"
  printf 'ok unsafe local dirs\n'
}

test_refuses_non_nfs_qnap() {
  setup
  load_standard_images
  make_set keepme 20261031 128
  run_untrusted --apply
  want_status 1
  grep -q -F -- 'refusing qnap root' "$ERR" || fail "missing nfs refusal"
  if grep -q -F -- 'image rm' "$MOCK_LOG"; then
    fail "image rm ran without an nfs qnap"
  fi
  [ -d "$QNAP/keepme/20261031" ] || fail "qnap set removed without nfs"
  printf 'ok non-nfs refusal\n'
}

test_lock_blocks_apply() {
  setup
  load_standard_images
  mkdir -p -- "$LOCAL/.plaude-image-retention.lock"
  printf '1\n' > "$LOCAL/.plaude-image-retention.lock/pid"
  run --apply
  want_status 1
  grep -q -F -- 'already running (pid 1)' "$ERR" || fail "missing lock error"
  if grep -q -F -- 'image rm' "$MOCK_LOG"; then
    fail "image rm ran while locked"
  fi
  printf 'ok lock\n'
}

test_dry_run_is_default_and_keeps_rollback_image() {
  setup
  load_standard_images
  absent=$TMP/not-created
  run --local-tar-dir "$absent"
  want_status 0
  [ ! -e "$absent" ] || fail "dry-run created the local tar dir"
  need "mode=dry-run"
  need "command=retain"
  need "newest_pre tag=plaude-web:pre-aaa888-20261030 image=$ID888"
  need "keep_image id=$ID111 tags=plaude-web:latest,plaude-web:pre-run111-20260901 reason=in-use size=1000"
  need "keep_image id=$ID888 tags=plaude-web:pre-aaa888-20261030 reason=newest-pre size=8000"
  need "keep_image id=$ID555 tags=- reason=in-use size=5000"
  need "list_image id=$ID444 tags=- dangling=yes"
  need "skip_image id=$ID666 tags=plaude-web:pre-mix666-20261031,other-product:kept reason=foreign-tag size=6000"
  need "remove_image id=$ID222 tags=plaude-web:pre-mid222-20261015 reason=unneeded size=2000 action=plan"
  need "remove_image id=$ID333 tags=plaude-web:pre-new333-20261030 reason=unneeded size=3000 action=plan"
  need "remove_image id=$ID444 tags=- reason=unneeded size=4000 action=plan"
  need "image_bytes_planned=9000"
  need "image_bytes_freed=0"
  need "bytes_freed=0"
  forbid "$ID777"
  forbid "action=done"
  if grep -q -F -- 'image rm' "$MOCK_LOG"; then
    fail "dry-run called image rm"
  fi
  assert_ps_and_ls
  printf 'ok dry-run image plan\n'
}

test_apply_removes_one_id_at_a_time() {
  setup
  load_standard_images
  run --apply
  want_status 0
  need "mode=apply"
  need "remove_image id=$ID222 tags=plaude-web:pre-mid222-20261015 reason=unneeded size=2000 action=done"
  need "remove_image id=$ID333 tags=plaude-web:pre-new333-20261030 reason=unneeded size=3000 action=done"
  need "remove_image id=$ID444 tags=- reason=unneeded size=4000 action=done"
  need "image_bytes_freed=9000"
  need "bytes_freed=9000"
  forbid "remove_image id=$ID111"
  forbid "remove_image id=$ID555"
  forbid "remove_image id=$ID666"
  forbid "remove_image id=$ID888"
  cmp -s "$FIX/removed" <(printf '%s\n' "$ID222" "$ID333" "$ID444") || fail "rm order was not one id at a time"
  if grep -E -q '(^| )(-f|--force)( |$)' "$MOCK_LOG"; then
    fail "docker was called with force"
  fi
  if grep -q -E 'image rm .+ ' "$MOCK_LOG"; then
    fail "image rm received more than an id"
  fi
  [ ! -d "$LOCAL/.plaude-image-retention.lock" ] || fail "lock left behind"
  printf 'ok apply image removal\n'
}

test_rm_failure_continues() {
  setup
  load_standard_images
  printf '%s\n' "$ID222" > "$FIX/fail-rm"
  run --apply
  want_status 1
  need "remove_image id=$ID222 tags=plaude-web:pre-mid222-20261015 reason=unneeded size=2000 action=failed"
  need "remove_image id=$ID333 tags=plaude-web:pre-new333-20261030 reason=unneeded size=3000 action=done"
  need "remove_image id=$ID444 tags=- reason=unneeded size=4000 action=done"
  need "image_bytes_freed=7000"
  printf 'ok rm failure continues\n'
}

test_qnap_count_or_bytes_and_protects_newest_verified() {
  setup
  make_set a 20261031 400
  make_set b 20261030 400
  make_set c 20261029 400
  make_set d 20261028 400
  one=$(measured "$QNAP/a/20261031")
  run --max-sets 3 --max-bytes $((one * 10))
  want_status 0
  need "qnap_remove path=$QNAP/d/20261028 reason=over-count size=$one action=plan"
  need "qnap_keep path=$QNAP/a/20261031 reason=newest-verified size=$one"
  [ -d "$QNAP/d/20261028" ] || fail "dry-run deleted a qnap set"
  run --apply --max-sets 3 --max-bytes $((one * 10))
  want_status 0
  [ -d "$QNAP/a/20261031" ] && [ -d "$QNAP/b/20261030" ] && [ -d "$QNAP/c/20261029" ] || fail "kept sets missing"
  [ ! -d "$QNAP/d/20261028" ] || fail "oldest set still present"
  need "qnap_bytes_freed=$one"

  setup
  make_set a 20261031 400
  make_set b 20261030 400
  make_set c 20261029 400
  make_set d 20261028 400
  one=$(measured "$QNAP/a/20261031")
  run --apply --max-sets 3 --max-bytes $((one * 2))
  want_status 0
  [ -d "$QNAP/a/20261031" ] && [ -d "$QNAP/b/20261030" ] || fail "byte cap dropped a set it should keep"
  [ ! -d "$QNAP/c/20261029" ] || fail "third set kept past the byte cap"
  [ ! -d "$QNAP/d/20261028" ] || fail "fourth set kept past the byte cap"
  need "qnap_remove path=$QNAP/c/20261029 reason=over-bytes size=$one action=done"

  setup
  make_set a 20261031 400
  make_set b 20261030 400
  make_set c 20261029 400
  one=$(measured "$QNAP/a/20261031")
  run --apply --max-sets 3 --max-bytes $((one * 3))
  want_status 0
  [ -d "$QNAP/a/20261031" ] && [ -d "$QNAP/b/20261030" ] && [ -d "$QNAP/c/20261029" ] || fail "exact byte cap dropped a set"

  setup
  make_set huge 20261031 5000
  run --apply --max-bytes 1000 --max-sets 3
  want_status 0
  [ -d "$QNAP/huge/20261031" ] || fail "deleted the only verified set"
  need "qnap_keep path=$QNAP/huge/20261031 reason=newest-verified"

  setup
  make_set huge 20261030 5000
  make_set small 20261029 100
  mkdir -p -- "$QNAP/new/20261031"
  head -c 50 </dev/zero > "$QNAP/new/20261031/plaude-web.tar"
  run --apply --max-bytes 1000 --max-sets 3
  want_status 0
  [ -d "$QNAP/huge/20261030" ] || fail "deleted newest verified set"
  [ ! -d "$QNAP/new/20261031" ] || fail "kept an incomplete newer set"
  [ ! -d "$QNAP/small/20261029" ] || fail "kept an older set past the byte cap"
  [ -d "$QNAP" ] || fail "removed the qnap root"

  setup
  make_set solo 20261031 200
  rm -- "$QNAP/solo/20261031/source/Dockerfile"
  rmdir -- "$QNAP/solo/20261031/source"
  run --apply --max-bytes 1
  want_status 0
  [ -f "$QNAP/solo/20261031/plaude-web.tar" ] || fail "deleted a hash-valid set that has no Dockerfile"
  need "reason=newest-verified"

  setup
  make_set good 20261031 100
  make_set bad 20261015 100
  printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  plaude-web.tar\n' \
    > "$QNAP/bad/20261015/plaude-web.tar.sha256"
  mkdir -p -- "$QNAP/zz/20260101.partial"
  printf 'junk\n' > "$QNAP/zz/20260101.partial/plaude-web.tar"
  run --apply --max-bytes $((1024 * 1024)) --max-sets 3
  want_status 0
  [ -d "$QNAP/good/20261031" ] || fail "removed the good set"
  [ ! -d "$QNAP/bad/20261015" ] || fail "kept a mismatched set"
  [ ! -d "$QNAP/zz/20260101.partial" ] || fail "kept a partial directory"
  [ ! -d "$QNAP/zz" ] || fail "left an empty pre-id directory"
  need "reason=mismatch"
  printf 'ok qnap policy\n'
}

test_unreadable_and_symlink_are_not_deleted() {
  setup
  make_set locked 20261031 128
  chmod 000 "$QNAP/locked/20261031/plaude-web.tar"
  mkdir -p -- "$QNAP/junk/20261001.partial"
  printf 'x\n' > "$QNAP/junk/20261001.partial/x"
  run --apply
  want_status 1
  [ -d "$QNAP/locked/20261031" ] || fail "deleted an unreadable set"
  [ ! -d "$QNAP/junk/20261001.partial" ] || fail "unreadable set blocked other cleanup"
  need "reason=unreadable"

  setup
  target=$TMP/symlink-target
  mkdir -p -- "$target" "$QNAP/evilid"
  printf 'secret\n' > "$target/keep-me"
  ln -s "$target" "$QNAP/evilid/20261020"
  make_set good 20261031 64
  run --apply
  want_status 1
  [ -f "$target/keep-me" ] || fail "followed a qnap symlink and deleted the target"
  [ -L "$QNAP/evilid/20261020" ] || fail "removed the symlink itself"
  [ -d "$QNAP/good/20261031" ] || fail "symlink warning blocked keeping a good set"
  printf 'ok unreadable and symlink\n'
}

test_local_tar_cap() {
  setup
  printf 'a\n' > "$LOCAL/a.tar"
  printf 'b\n' > "$LOCAL/b.tar"
  printf 'c\n' > "$LOCAL/c.tar"
  printf 'old\n' > "$LOCAL/a.tar.sha256"
  printf 'keep\n' > "$LOCAL/c.tar.sha256"
  printf 'part\n' > "$LOCAL/old.tar.partial"
  touch -d '2026-01-01 00:00:00' "$LOCAL/a.tar"
  touch -d '2026-02-01 00:00:00' "$LOCAL/b.tar"
  touch -d '2026-03-01 00:00:00' "$LOCAL/c.tar"
  run --apply
  want_status 0
  [ -f "$LOCAL/c.tar" ] || fail "newest local tar was removed"
  [ -f "$LOCAL/c.tar.sha256" ] || fail "checksum of the kept tar was removed"
  [ ! -f "$LOCAL/a.tar" ] && [ ! -f "$LOCAL/b.tar" ] || fail "extra local tars remain"
  [ ! -f "$LOCAL/a.tar.sha256" ] || fail "orphan checksum remains"
  [ ! -f "$LOCAL/old.tar.partial" ] || fail "partial remains beside a completed tar"
  need "local_tar_keep path=$LOCAL/c.tar reason=newest-local"
  printf 'ok local tar cap\n'
}

test_backup_dry_run_then_apply() {
  setup
  load_standard_images
  make_set previous 20260115 128
  run backup
  want_status 0
  need "mode=dry-run"
  need "command=backup"
  need "backup_tag=plaude-web:pre-aaa888-20261030"
  need "backup_pre_id=aaa888"
  need "backup_date=20261030"
  need "qnap_publish path=$QNAP/aaa888/20261030 action=plan"
  [ ! -e "$QNAP/aaa888" ] || fail "dry-run backup created a qnap directory"
  if grep -q -F -- 'save ' "$MOCK_LOG"; then
    fail "dry-run backup called docker save"
  fi
  if [ -s "$IONICE_LOG" ]; then
    fail "dry-run backup throttled a copy"
  fi

  : > "$MOCK_LOG"
  : > "$IONICE_LOG"
  run backup --apply
  want_status 0
  need "qnap_publish path=$QNAP/aaa888/20261030 action=done"
  need "local_tar_remaining=0"
  [ -f "$QNAP/aaa888/20261030/plaude-web.tar" ] || fail "missing published tar"
  [ -f "$QNAP/aaa888/20261030/plaude-web.tar.sha256" ] || fail "missing published sha256"
  cmp -s "$ROOT/Dockerfile" "$QNAP/aaa888/20261030/source/Dockerfile" || fail "Dockerfile was not copied"
  ( cd "$QNAP/aaa888/20261030" && sha256sum -c plaude-web.tar.sha256 >/dev/null ) || fail "published sha256 does not match"
  [ -d "$QNAP/previous/20260115" ] || fail "backup deleted an older qnap set"
  [ ! -e "$QNAP/aaa888/20261030.partial" ] || fail "partial directory left after publish"
  find "$LOCAL" -name '*.tar' -print | grep -q . && fail "local tar left after verified backup"
  grep -q -F -- 'save plaude-web:pre-aaa888-20261030' "$MOCK_LOG" || fail "saved the wrong tag"
  if grep -q -F -- 'image rm' "$MOCK_LOG"; then
    fail "backup removed an image"
  fi
  rsyncs=$(grep -c -F -- 'rsync --bwlimit=10m' "$IONICE_LOG" || true)
  [ "$rsyncs" -eq 3 ] || fail "expected 3 throttled rsync copies, got $rsyncs"
  grep -q -F -- '-c3' "$IONICE_LOG" || fail "ionice was not idle class"
  grep -q -F -- 'dd if=' "$IONICE_LOG" || fail "sha256 read was not passed through ionice dd"
  if grep -q -F -- 'image rm' "$IONICE_LOG"; then
    fail "ionice log contains image rm"
  fi

  : > "$MOCK_LOG"
  : > "$IONICE_LOG"
  run backup --apply
  want_status 0
  [ -d "$QNAP/aaa888/20261030" ] || fail "second backup removed the set"
  [ ! -e "$QNAP/aaa888/20261030.partial" ] && [ ! -e "$QNAP/aaa888/20261030.replacing" ] || fail "second backup left a partial"
  ( cd "$QNAP/aaa888/20261030" && sha256sum -c plaude-web.tar.sha256 >/dev/null ) || fail "replaced backup does not verify"
  [ -d "$QNAP/previous/20260115" ] || fail "second backup deleted an older set"
  need "local_tar_remaining=0"

  : > "$MOCK_LOG"
  run --apply --max-sets 1 --max-bytes $((1024 * 1024 * 1024))
  want_status 0
  [ -d "$QNAP/aaa888/20261030" ] || fail "retention deleted the newest verified backup"
  [ ! -d "$QNAP/previous/20260115" ] || fail "retention kept more than one set"
  grep -q -F -- 'image rm' "$MOCK_LOG" || fail "retention did not remove old images"
  cmp -s "$FIX/removed" <(printf '%s\n' "$ID222" "$ID333" "$ID444") || fail "retention removed the wrong images"
  printf 'ok backup then retention\n'
}

test_backup_verify_failure_keeps_one_local_tar() {
  setup
  load_standard_images
  make_set previous 20260115 64
  printf 'a\n' > "$LOCAL/a.tar"
  printf 'b\n' > "$LOCAL/b.tar"
  printf 'c\n' > "$LOCAL/c.tar"
  touch -d '2026-01-01 00:00:00' "$LOCAL/a.tar"
  touch -d '2026-02-01 00:00:00' "$LOCAL/b.tar"
  touch -d '2026-03-01 00:00:00' "$LOCAL/c.tar"
  cat > "$BIN/sha-fail" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "-c" ]; then
  printf 'plaude-web.tar: FAILED\n' >&2
  exit 1
fi
exec /usr/bin/sha256sum "$@"
EOF
  chmod +x "$BIN/sha-fail"
  PLAUDE_SHA256SUM=$BIN/sha-fail
  export PLAUDE_SHA256SUM
  run backup --apply
  unset PLAUDE_SHA256SUM
  want_status 1
  need "local_tar_remaining=1"
  need "qnap_publish path=$QNAP/aaa888/20261030 action=failed"
  [ -f "$LOCAL/plaude-web.tar" ] || fail "failed backup did not keep the new local tar"
  [ ! -f "$LOCAL/a.tar" ] && [ ! -f "$LOCAL/b.tar" ] && [ ! -f "$LOCAL/c.tar" ] || fail "failed backup left more than one local tar"
  [ ! -d "$QNAP/aaa888/20261030" ] || fail "failed verify published the set"
  [ -d "$QNAP/aaa888/20261030.partial" ] || fail "failed verify removed its partial"
  [ -d "$QNAP/previous/20260115" ] || fail "failed backup touched the previous set"
  printf 'ok backup verify failure\n'
}

test_backup_save_failure_keeps_previous_local_tar() {
  setup
  load_standard_images
  printf 'old\n' > "$LOCAL/old.tar"
  printf 'older\n' > "$LOCAL/older.tar"
  touch -d '2026-01-01 00:00:00' "$LOCAL/older.tar"
  touch -d '2026-02-01 00:00:00' "$LOCAL/old.tar"
  : > "$FIX/save-fail"
  run backup --apply
  want_status 1
  [ -f "$LOCAL/old.tar" ] || fail "save failure deleted the only remaining local tar"
  [ ! -f "$LOCAL/older.tar" ] || fail "save failure left an extra local tar"
  [ ! -f "$LOCAL/plaude-web.tar" ] || fail "failed save left a completed tar"
  [ ! -e "$QNAP/aaa888" ] || fail "failed save published to qnap"
  grep -q -F -- 'docker save failed' "$ERR" || fail "missing save failure"
  printf 'ok backup save failure\n'
}

test_backup_rejects_tiny_save() {
  setup
  load_standard_images
  SAVE_BYTES=10
  export SAVE_BYTES
  run backup --apply
  unset SAVE_BYTES
  want_status 1
  grep -q -F -- 'wrote only 10 bytes' "$ERR" || fail "missing short-save error"
  [ ! -e "$QNAP/aaa888" ] || fail "short save was published"
  printf 'ok short save\n'
}

test_backup_requires_a_pre_tag_and_dockerfile() {
  setup
  add_image "$(hid 111)" "2026-10-31T00:00:00Z" 1000 "plaude-web:latest" plaude yes repo
  run backup --apply
  want_status 1
  grep -q -F -- 'no plaude-web:pre-' "$ERR" || fail "missing missing-tag error"
  if grep -q -F -- 'save ' "$MOCK_LOG"; then
    fail "save ran without a pre tag"
  fi
  setup
  load_standard_images
  rm -- "$ROOT/Dockerfile"
  run backup --apply
  want_status 1
  grep -q -F -- 'Dockerfile not found' "$ERR" || fail "missing dockerfile error"
  if grep -q -F -- 'save ' "$MOCK_LOG"; then
    fail "save ran without a Dockerfile"
  fi
  printf 'ok backup preconditions\n'
}

test_save_is_rate_limited() {
  setup
  load_standard_images
  SAVE_BYTES=$((2 * 1024 * 1024))
  export SAVE_BYTES
  start=$(date +%s%N)
  run backup --apply
  end=$(date +%s%N)
  unset SAVE_BYTES
  want_status 0
  elapsed=$((end - start))
  # 2 MiB through the saver and again through sha256: four 0.1s pauses.
  [ "$elapsed" -ge 350000000 ] || fail "backup finished too fast (${elapsed}ns); the 10MiB/s cap did not run"
  ( cd "$QNAP/aaa888/20261030" && sha256sum -c plaude-web.tar.sha256 >/dev/null ) || fail "rate-limited backup did not verify"
  printf 'ok rate limit\n'
}

test_dry_run_does_not_create_directories_on_apply_path() {
  setup
  created=$TMP/created-by-apply
  run --apply --local-tar-dir "$created"
  want_status 0
  [ -d "$created" ] || fail "apply did not create the local tar dir"
  [ ! -d "$created/.plaude-image-retention.lock" ] || fail "apply left the lock"
  printf 'ok apply creates only the local dir\n'
}

if grep -nE 'docker[[:space:]]+(system|builder|stop|kill)|image[[:space:]]+prune|compose[[:space:]]+down' "$SCRIPT"; then
  printf 'FAIL: forbidden command in %s\n' "$SCRIPT" >&2
  exit 1
fi

test_help_and_flags
test_refuses_unsafe_local_dirs
test_refuses_non_nfs_qnap
test_lock_blocks_apply
test_dry_run_is_default_and_keeps_rollback_image
test_apply_removes_one_id_at_a_time
test_rm_failure_continues
test_qnap_count_or_bytes_and_protects_newest_verified
test_unreadable_and_symlink_are_not_deleted
test_local_tar_cap
test_backup_dry_run_then_apply
test_backup_verify_failure_keeps_one_local_tar
test_backup_save_failure_keeps_previous_local_tar
test_backup_rejects_tiny_save
test_backup_requires_a_pre_tag_and_dockerfile
test_save_is_rate_limited
test_dry_run_does_not_create_directories_on_apply_path
printf 'all tests passed\n'
