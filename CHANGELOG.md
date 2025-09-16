# Changelog:

## 0.3.1
* Fix --from and --to handling under Typer.

## 0.3.0
* Port to Typer instead of argparse.
* Added help command.
* Teaser after updates encouraging to see `whats-new`.
* --time option available for `punch add`
* Interactive selection shown after providing category code

## 0.2.8
* Fixed version reporting (was hardcoded to 0.1.3).
* Ensure consistent way of handling `-d/--day` for `export`, `submit` & `report` options.
* Improve handling of an incorrect day/date string.
* Show total time in minutes for `submit`.

## 0.2.7
* Added date_format config option to punch.yaml (an interim solution before figuring out automatic locale detection for SF in the integrated browser).

## 0.2.6
* Report issues with timecards not mapped to a SF case.
* Add a new option `-d/--day` to set a single day for `report`, `export` and `submit`.

## 0.2.5
* Fixed [#3](https://github.com/dargad/punch/issues/3)
* Config wizard to set the required options (including creating the categories)
* Added timecard duration rounding (to round e.g. to the nearest 5 mins)
* Updated test script and unit tests.

## 0.2.4
* Fixed bash completion behavior - ":" can be now either a separate argument or part of the category
* Introduced a "config" command with basic features allowing to e.g. show configuration or set a `<key> <value>` in it.

## 0.2.3
* Fixed bash completion working out-of-the-box from snap
* Tasks are checked for chronological order while they're being loaded
* If a malformed task is encountered the line number is printed.
* zsh task completions are offered most recent first

## 0.2.2
* Fixed passing on config to _reload_timecards
* Changed task name formatting in the submit progress bar

## 0.2.1
* Implemented exporting to files.
* New github workflow actions running CLI sanity checks
* Merged fix for unittests complaining about tempdir (thanks to @jameinel)
* In `submit` summary for timecards not related to SF cases category is used as 2nd column.

## 0.2.0
* Added `help` command.
* Start time passed as an argument to `punch start`, e.g. `punch start --time 8:30`
* Interactive submission mode (data is pre-filled, user clicks **Save**)
* Timecards summary displayed before actually starting submitting them.
* `--sleep` option to enforce delay between timecards submissions in headed mode
* Fixed `submit --dry-run`.
Many thanks to @jameinel for contribution.
