---
title: NRRDTASK
section: 1
header: User Manual
footer: nrrdtask 0.0.3
date: January 3, 2022
---
# NAME
nrrdtask - Terminal-based task management for nerds.

# SYNOPSIS
**nrrdtask** *command* [*OPTION*]...

# DESCRIPTION
**nrrdtask** is a terminal-based task management program with advanced search options, formatted output, and task data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrdtask** provides the following commands.

**archive** *alias* [*OPTION*]
: Move a task to the archive directory of your data directory (by default, $HOME/.local/share/nrrdtask/archive). The user will be prompted for confirmation. Archiving a task removes it from all views, and is designed as a method to save completed tasks while removing old tasks from **list** output.

    *OPTIONS*

    **-f**, **--force**
    : Force the archive operation, do not prompt for confirmation.


**complete** *alias*
: Complete a task (set *status* to 'done', *percent* to '100', and *completed* to the current datetime).

**config**
: Edit the **nrrdtask** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete a task and task file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.


**edit** *alias*
: Edit a task file in the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**export** *searchterm*
: Search and output results in VTODO format, to STDOUT.

**info** *alias* [*OPTION*]
: Show the full details about a task (and its subtasks, if any).

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**list (ls)** <*alias* | *view*> [*OPTION*]
: List tasks matching a specific *alias* or one of the following views:

    - *open* : All open tasks (status is not 'done').
    - *all* : All tasks.
    - *done* : Tasks that have a status of 'done'.
    - *nosubs* : All open tasks (except subtasks).
    - *late* : Tasks that have a *start* date in the past with a status of 'todo' or a *due* date in the past with a status that is not 'done'.
    - *soon* : Tasks that have a *start* or *due* date that is "soon" (as defined by the *days_soon* configuration parameter) and has a status of 'todo' (for *start*) or is not done (for *due*).
    - *today* : Like *soon* but with a *start* or *due* date of today.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

    **--project**
    : Filter list to specific project.

**modify (mod)** *alias* [*OPTION*]...
: Modify a task.

    *OPTIONS*

    **--completed** *YYYY-MM-DD[ HH:MM]*
    : The task completed date(time).

    **--description** *text*
    : The task description.

    **--due** *YYYY-MM-DD[ HH:MM]*
    : The task due date(time).

    **--location** *location*
    : The task location.

    **--notes** *text*
    : Notes to add to the task. Be sure to properly escape the text if it includes special characters or newlines that may be interpretted by the shell. Using this option, any existing notes on the task will be replaced. This command option is included mainly for the purpose of automated note insertion (i.e., via script or command). For more reliable note editing, use the **notes** command.
    
    **--parent** *alias*
    : The parent alias of the task (denoting this task as a subtask).

    **--percent** *number*
    : The task percent complete.

    **--priority** *number*
    : The task priority. 1 is the highest priority. Priority is defined as *high*, *medium*, *normal*, and *low*. Thresholds for these values are defined by the following configuration options: *priority_high*, *priority_medium*, and *priority_normal*. A priority is defined by the following expression:

            HIGH <= priority_high < MEDIUM <= priority_medium < NORMAL <= priority_normal < LOW

        If color is enabled, task priority is color-coded.

    **--project** *project*
    : The project associated with this task.

    **--rrule** *rule*
    : The task's recurrence rule. See *Task Recurrence* under **NOTES**.

    **--start** *YYYY-MM-DD[ HH:MM]*
    : The task start date(time).

    **--started** *YYYY-MM-DD[ HH:MM]*
    : The task started date(time).

    **--status** *status*
    : The task status. The status text is arbitrary, but the following statuses are recognized by **nrrdtask**:

        - *done* : the task is completed.
        - *todo* : the task is unstarted.
        - *inprogress* : the task is started but not complete.
        - *waiting* : the task is waiting for some condition.
        - *onhold* : the task is on hold.
        - *blocked* : the task is blocked by some issue.
        - *cancelled* : the task has been cancelled.

    **--tags** *tag[,tag]*
    : Tags assigned to the task. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the task will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +documentation* will add the *documentation* tag to the existing tags on a task, and *--tags ~testing,experimental* will remove both the *testing* and *experimental* tags from a task.

    **--add-reminder** <*YYYY-MM-DD HH:MM* | *expression*> *notification*
    : Add a reminder to a task. The reminder can be defined as a specific date and time, or as a relative expression:

        - start+/-[Xd][Yh][Zm] : a reminder relative to *start*. E.g., 'start-15m' triggers a reminder 15 minutes before the *start* datetime.
        - due+/-[Xd][Yh][Zm] : a reminder relative to *due*. E.g., 'due+1h' triggers a reminder 1 hour after the *due* datetime.

        The *notification* can be one of *display* or *email*. A *display* notification will trigger a desktop notification and an *email* notification will cause a reminder email to be sent. **NOTE**: **nrrdtask** itself does not send reminders, but produces a JSON-formatted list of reminder triggers and notification types using the **reminders** command. The output of **reminders** can be parsed by an application such as **nrrdalrt** which will produce the notifications.

    **--del-reminder** *index*
    : Delete a reminder from a task. The reminder is identified by the index displayed in the output of **info**.

**new** *description* [*OPTION*]...
: Create a new task.

    *OPTIONS*

    **--completed** *YYYY-MM-DD[ HH:MM]*
    : The task completed date(time).

    **--due** *YYYY-MM-DD[ HH:MM]*
    : The task due date(time).

    **--location** *location*
    : The task location.

    **--notes** *text*
    : Notes to add to the task. See the **--notes** option of **modify**.
    
    **--parent** *alias*
    : The parent alias of the task (denoting this task as a subtask).

    **--percent** *number*
    : The task percent complete.

    **--priority** *number*
    : The task priority. See the **--priority** option of **modify**.

    **--project** *project*
    : The project associated with this task.

    **--reminder** <*YYYY-MM-DD HH:MM* | *expression*> *notification*
    : Add a reminder to a task. See the **--add-reminder** option of **modify**.

    **--rrule** *rule*
    : The task's recurrence rule. See *Task Recurrence* under **NOTES**.

    **--start** *YYYY-MM-DD[ HH:MM]*
    : The task start date(time).

    **--started** *YYYY-MM-DD[ HH:MM]*
    : The task started date(time).

    **--status** *status*
    : The task status. See the **--status** option of **modify**.

    **--tags** *tag[,tag]*
    : Tags assigned to the task. See the **--tags** option of **modify**.


**notes** *alias*
: Add or update notes on a task using the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**query** *searchterm* [*OPTION*]...
: Search for one or more tasks and produce plain text output (by default, tab-delimited text).

    *OPTIONS*

    **-l**, **--limit**
    : Limit the output to one or more specific fields (provided as a comma-delimited list).

    **-j**, **--json**
    : Output in JSON format rather than the default tab-delimited format.


**reminders (rem)** *interval*
: Output to STDOUT task reminders in JSON format for the next interval expressed in the form [Xd][Yh][Zm] (for days, hours, and minutes).

    **Examples:**

    Both of these provide any reminders scheduled for the next hour.

        nrrdtask reminders 60m
        nrrdtask reminders 1h

    Show reminders scheduled for the next 2 days, 12 hours, and 45 minutes:

        nrrdtask reminders 2d12h45m

**search** *searchterm* [*OPTION*]
: Search for one or more tasks and output a tabular list (same format as **list**).

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrdtask** interactive shell.

**start** *alias*
: Start a task (set *status* to 'inprogress' and set *started* to the current datetime).

**unset** *alias* *field*
: Clear a field from a specified task.

**version**
: Show the application version information.

# NOTES

## Archiving a task
Use the **archive** subcommand to move the task file to the subdirectory archive in the the tasks data directory. Confirmation will be required for this operation unless the *--force* option is also used.

Archived tasks will no longer appear in lists of tasks (*done* or otherwise). This can be useful for retaining completed tasks without resulting in endlessly growing task lists. To review archived tasks, create an alterate config file with a *data_dir* pointing to the archive folder, and an alias such as:

    alias nrrdtask-archive="nrrdtask -c $HOME/.config/nrrdtask/config.archive"

**NOTE:** If you archive a task that has subtasks, the subtasks will also be archived.

## Task recurrence
Tasks may have a recurrence rule (using the **--rrule** option to **new** and **modify**) to express that the task repeats or occurs more than once. The *rrule* is a semicolon-delimited list of key/value pairs.

The supported keys are:

    - date= : (str) specific recurrence date/times, delimited by comma (,).
    - except= : (str) specific date/times to be excluded, delimited by comma (,).
    - freq= : (str) one of minutely, hourly, daily, weekly, monthly, or yearly.
    - count= : (int) a specific number of recurrences.
    - until= : (str) recur until this date/time.
    - interval= : (int) the interval of recurrence.
    - byhour= : (int) recur by hour (0-23).
    - byweekday= : (str) one or more (comma-delimited) of SU, MO, TU, WE, TH, FR, or SA.
    - bymonth= : (int) recur by month (1-12).
    - bymonthday= : (int) recur by day of month (1-31).
    - byyearday= : (int) recur by day of the year (1-366).
    - byweekno= : (int) recur by week of year (1-53).
    - bysetpos= : (int) the position in an occurence set (e.g., 1 for first, -1 for last, -2 for second to last).

For example, a task that recurs on the last Monday of the month until December 31, 2021 would have the following rrule:

    freq=monthly;byweekday=MO;bysetpos=-1;until=2021-12-31

**NOTE:** ensure to properly escape or quote ';' in recurrence rules when using the --rrule option on the command line.

A task MUST have both a *start* date/time and an *rrule* to be considered a recurring task. A task with an *rrule* and no *start* will be treated as a regular task.

### How repeating tasks work
Only one active (non-'done') instance of a repeating task will appear in the task list at any given time. When the *status* of a repeating task is set to 'done' or 'cancelled', **nrrdtask** will clone the task into a new task with a *status* of 'todo', and 'start' and 'due' set to the next occurrence date and relative due date (if any). Other progress fields (e.g., *started*, *completed*, *percent*, etc.) will be reset. Completed recurring tasks remain in history and exist in the *data_dir* like any other task.

## Search and query
There are two command-line methods for filtering the presented list of tasks: **search** and **query**. These two similar-sounding functions perform very different roles.

Search results are output in the same tabular, human-readable format as that of **list**. Query results are presented in the form of tab-delimited text (by default) or JSON (if using the *-j* or *--json* option) and are primarily intended for use by other programs that are able to consume structured text output.

**search** and **query** use the same filter syntax. The most basic form of filtering is to simply search for a keyword or string in the task description:

    nrrdtask search <search_term>

**NOTE:** search terms are case-insensitive.

If the search term is present in the task *description*, the task will be displayed.

Optionally, a search type may be specified. The search type may be one of *uid*, *alias*, *description*, *location*, *tags*, *status*, *parent*, *priority*, *percent*, *project*, *start*, *due*, *started*, *completed*, or *notes*. If an invalid search type is provided, the search type will default to *description*. To specify a search type, use the format:

    nrrdtask search [search_type=]<search_term>

You may combine search types in a comma-delimited structure. All search criteria must be met to return a result.

The tags search type may also use the optional **+** operator to search for more than one tag. Any matched tag will return a result.

The special search term *any* can be used to match all tasks, but is only useful in combination with an exclusion to match all records except those excluded.

## Exclusion
In addition to the search term, an exclusion term may be provided. Any match in the exclusion term will negate a match in the search term. An exclusion term is formatted in the same manner as the search term, must follow the search term, and must be denoted using the **%** operator:

    nrrdtask search [search_type=]<search_term>%[exclusion_type=]<exclusion_term>

## Search examples
Search for any task description with the word "projectx":

    nrrdtask search projectx

Search for any tasks due 2021-11-15:

    nrrdtask search due=2021-11-15

Search for all tasks tagged "development" or "testing" with a status of "inprogess" and a priority of 1-3, except for those that are 95% or more complete:

    nrrdtask search status=inprogress,priority=~3,tags=development+testing%percent=95~

## Query and limit
The query function uses the same syntax as search but will output information in a form that may be read by other programs. The standard fields returned by query for tab-delimited output are:

    - uid (string)
    - alias (string)
    - status (string)
    - priority (string)
    - description (string)
    - location (string)
    - project (string)
    - percent (string)
    - tags (list)
    - parent (string)
    - start (string)
    - due (string)
    - started (string)
    - completed (string)

List fields are returned in standard Python format: ['item 1', 'item 2', ...]. Empty lists are returned as []. Empty string fields will appear as multiple tabs.

JSON output returns all fields for a record, including fields not provided in tab-delimited output.

The query function may also use the **--limit** (**-l**) option. This is a comma-separated list of fields to return. The **--limit** option does not have an effect on JSON output.

## Paging
Output from **list**, **search**, and **info** can get long and run past your terminal buffer. You may use the **-p**, **--page** option in conjunction with search, list, or info to page output.


# FILES
**~/.config/nrrdtask/config**
: Default configuration file

**~/.local/share/nrrdtask**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrdtask/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrdtask>
