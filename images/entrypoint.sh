#!/usr/bin/env bash

set -e

if [ "$1" = "cfn-check" ]; then
  # Remove the command from the option list (we know it)
  shift

  # Then run it with default options plus whatever else
  # was given in the command
  exec cfn-check "$@"
fi

exec cfn-check "$@"