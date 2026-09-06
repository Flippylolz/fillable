#!/bin/sh
set -eu
test "$#" -gt 0
for result in "$@"; do
  test "$result" = success
done
