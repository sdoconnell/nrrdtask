#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrdtask
Version:  0.0.3
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrdtask
About:
A terminal-based task management tool with local file-based storage.

usage: nrrdtask [-h] [-c <file>] for more help: nrrdtask <command> -h ...

Terminal-based task management for nerds.

commands:
  (for more help: nrrdtask <command> -h)
    archive             archive a task
    complete            complete a task
    delete (rm)         delete a task file
    edit                edit a task file (uses $EDITOR)
    export              export tasks to iCalendar-formatted VTODO output
    info                show info about a task
    list (ls)           list tasks
    modify (mod)        modify a task
    new                 create a new task
    notes               add/update notes on a task (uses $EDITOR)
    query               search tasks with structured text output
    reminders (rem)     task reminders
    search              search tasks
    shell               interactive shell
    start               start a task
    unset               clear a field from a specified task
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file


Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import configparser
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import uuid
from cmd import Cmd
from datetime import datetime, timedelta, timezone
from textwrap import TextWrapper

import tzlocal
import yaml
from dateutil import parser as dtparser
from dateutil.rrule import rrule as rr_rrule
from dateutil.rrule import MINUTELY, HOURLY, DAILY
from dateutil.rrule import WEEKLY, MONTHLY, YEARLY
from dateutil.rrule import SU, MO, TU, WE, TH, FR, SA
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrdtask"
APP_VERS = "0.0.3"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DURATION = 30
DEFAULT_REMINDER = "start-15m"
DEFAULT_FIRST_WEEKDAY = 6
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    "# how many days before due date is 'soon'\n"
    "#days_soon = 1\n"
    "# first day of week (0 = Mon, 6 = Sun)\n"
    f"first_weekday = {DEFAULT_FIRST_WEEKDAY}\n"
    "# priority thresholds (<=)\n"
    "#priority_high = 3\n"
    "#priority_medium = 6\n"
    "#priority_normal = 9\n"
    "# default notification duration (in minutes)\n"
    "default_duration = 30\n"
    "# default event reminder expression\n"
    f"default_reminder = {DEFAULT_REMINDER}\n"
    "# set your email address for reminder emails\n"
    "#user_email = bob@roberts.tld\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#title = blue\n"
    "#description = default\n"
    "#location = default\n"
    "#alias = bright_black\n"
    "#tags = cyan\n"
    "#parent = cyan\n"
    "#label = white\n"
    "#date = green\n"
    "#date_soon = yellow\n"
    "#date_late = red\n"
    "#status_done = green\n"
    "#status_todo = red\n"
    "#status_inprogress = cyan\n"
    "#status_waiting = magenta\n"
    "#status_onhold = blue\n"
    "#status_blocked = yellow\n"
    "#status_cancelled = bright_black\n"
    "#priority_high = bright_red\n"
    "#priority_medium = bright_yellow\n"
    "#priority_normal = bright_green\n"
    "#priority_low = bright_blue\n"
    "#percent = cyan\n"
    "#percent_100 = bright_cyan\n"
    "#flag = bright_yellow\n"
    "\n"
    "[project_colors]\n"
    "#projectx = bright_red\n"
    "#vegasbuild = yellow\n"
)


class Tasks():
    """Performs task operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing task files.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes a Tasks() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # default colors
        self.color_title = "bright_blue"
        self.color_description = "default"
        self.color_location = "default"
        self.color_alias = "bright_black"
        self.color_tags = "cyan"
        self.color_parent = "cyan"
        self.color_label = "white"
        self.color_date = "green"
        self.color_date_soon = "yellow"
        self.color_date_late = "red"
        self.color_status_done = "green"
        self.color_status_todo = "red"
        self.color_status_inprogress = "cyan"
        self.color_status_waiting = "magenta"
        self.color_status_onhold = "blue"
        self.color_status_blocked = "yellow"
        self.color_status_cancelled = "bright_black"
        self.color_priority_low = "bright_blue"
        self.color_priority_normal = "bright_green"
        self.color_priority_medium = "bright_yellow"
        self.color_priority_high = "bright_red"
        self.color_percent = "cyan"
        self.color_percent_100 = "bright_cyan"
        self.color_flag = "bright_yellow"
        self.color_bold = True
        self.color_pager = False
        self.project_colors = None
        self.color_enabled = True

        # default settings
        self.ltz = tzlocal.get_localzone()
        self.first_weekday = DEFAULT_FIRST_WEEKDAY
        self.days_soon = 1
        self.priority_high = 3
        self.priority_medium = 6
        self.priority_normal = 9
        self.default_duration = DEFAULT_DURATION
        self.default_reminder = DEFAULT_REMINDER
        self.user_email = None
        self.add_reminders = None
        self.recurrence_limit = 100

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # initial style definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_title = None
        self.style_description = None
        self.style_location = None
        self.style_alias = None
        self.style_tags = None
        self.style_parent = None
        self.style_label = None
        self.style_date = None
        self.style_date_soon = None
        self.style_date_late = None
        self.style_date_done = None
        self.style_status_done = None
        self.style_status_todo = None
        self.style_status_inprogress = None
        self.style_status_waiting = None
        self.style_status_onhold = None
        self.style_status_blocked = None
        self.style_status_cancelled = None
        self.style_status_default = None
        self.style_priority_low = None
        self.style_priority_normal = None
        self.style_priority_medium = None
        self.style_priority_high = None
        self.style_percent = None
        self.style_percent_100 = None
        self.style_flag = None

        # parent tasks
        self.parents = {}

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()

    def _alias_not_found(self, alias):
        """Report an invalid alias and exit or pass appropriately.

        Args:
            alias (str):    the invalid alias.

        """
        self._handle_error(f"Alias '{alias}' not found")

    def _build_flat(
            self,
            tasklist,
            sortby,
            filtexp=None,
            project=None):
        """Build a flat dict of sorted tasks filtered by an expression.

        Args:
            tasklist (list): the list of tasks to parse.
            sortby (str):    the parameter by which to sort tasks.
            filtexp (str):   an expression of tasks to filter.
            project (str):   filter list to only show tasks in project.

        Returns:
            flat (dict):     the flat list of tasks.

        """
        uids = self._sort_tasks(tasklist, sortby)
        flat = {}
        for uid in uids:
            task = self._parse_task(uid)
            add_task = True
            if project:
                if project != task['project']:
                    add_task = False
            if add_task:
                if self._pass_filter(filtexp, task['status']):
                    flat[uid] = []
        return flat

    def _build_tree(
            self,
            tasklist,
            sortby,
            filtexp=None,
            subs=True,
            project=None):
        """Build a tree dict of sorted tasks filtered by an expression.

        Args:
            tasklist (list): the list of tasks to parse.
            sortby (str):    the parameter by which to sort tasks.
            filtexp (str):   an expression of tasks to filter.
            subs (bool):     whether or not to include subtasks.
            project (str):   filter list to only show tasks in project.

        Returns:
            tree (dict):    the hierarchal tree of tasks.

        """
        uids = self._sort_tasks(tasklist, sortby)
        tree = {}
        for uid in uids:
            task = self._parse_task(uid)
            add_task = True
            if project:
                if project != task['project']:
                    add_task = False
            if add_task:
                if (not task['parent'] and
                        self._pass_filter(filtexp, task['status'])):
                    tree[uid] = []
                    if subs and uid in self.parents:
                        subtasks = self.parents[uid]
                        children = self._sort_tasks(subtasks, sortby)
                        for child in children:
                            subtask = self._parse_task(child)
                            if self._pass_filter(
                                    filtexp, subtask['status']):
                                tree[uid].append(child)
        return tree

    def _calc_duration(self, expression):
        """Calculates the duration in seconds represented by an
        expression in the form (x)d(y)h(z)m, (y)h(z)m, or (z)m for days,
        hours, and minutes.

        Args:
            expression (str):   the duration expression.

        Returns:
            duration (int):      the duration in seconds.

        """
        expression = expression.lower()
        d_search = re.search(r"\d+d", expression)
        h_search = re.search(r"\d+h", expression)
        m_search = re.search(r"\d+m", expression)
        days = int(d_search[0].replace('d', '')) if d_search else 0
        hours = int(h_search[0].replace('h', '')) if h_search else 0
        minutes = int(m_search[0].replace('m', '')) if m_search else 0
        duration = (days*86400) + (hours*3600) + (minutes*60)

        if duration == 0:
            duration = self.default_duration*60

        return duration

    def _calc_next_recurrence(self, rrule, dt_start, dt_due):
        """Calculates the next recurrence for a task given start and
        due datetimes and a recurrence rule.

        Args:
            rrule (obj):        the recurrence rule object.
            dt_start (obj):     the start datetime.
            dt_due (obj):       the due datetime.

        Returns:
            next_start (obj):   the next start datetime.
            next_due (obj):     the next due datetime.

        """
        recurrences = self._calc_task_recurrences(rrule, dt_start)
        next_start = None
        next_due = None
        if recurrences:
            for next_dt in recurrences:
                if next_dt > dt_start:
                    next_start = next_dt
                    break
            if dt_due:
                duration = dt_due - dt_start
                next_due = next_start + duration

        return next_start, next_due

    def _calc_relative_datetime(self, reference, duration, prior=False):
        """Calculates a relative datetime using a reference time and an
        expression in the form (x)d(y)h(z)m, (y)h(z)m, or (z)m for days,
        hours, and minutes.

        Args:
            reference (obj):    datetime object for the reference time.
            duration (int):     duration expression.
            prior (bool):       the relative datetime should be
        calculated prior to the reference datetime.

        Returns:
            reminder (obj):     datetime object for the reminder.

        """
        seconds = self._calc_duration(duration)
        if prior:
            relative = reference - timedelta(seconds=seconds)
        else:
            relative = reference + timedelta(seconds=seconds)

        return relative

    def _calc_reminder(self, reminder, dt_start=None, dt_due=None):
        """Calculates a reminder datetime object given a reminder
        expression and start or due datetime object.

        Args:
            reminder (str): the reminder expression.
            dt_start (obj): the task start datetime.
            dt_due (obj):   the task due datetime.

        Returns:
            dt_reminder (obj):  the reminder datetime.

        """
        reminder = reminder.lower()
        dt_reminder = self._datetime_or_none(reminder)
        if not dt_reminder:
            if '-' in reminder:
                split = '-'
                prior = True
                parse = True
            elif '+' in reminder:
                split = '+'
                prior = False
                parse = True
            else:
                parse = False
            if parse:
                reminder = reminder.split(split)
                if reminder[0] == "start" and dt_start:
                    dt_reminder = self._calc_relative_datetime(
                            dt_start, reminder[1], prior)
                elif reminder[0] == "due" and dt_due:
                    dt_reminder = self._calc_relative_datetime(
                            dt_due, reminder[1], prior)
                else:
                    dt_reminder = None

        return dt_reminder

    def _calc_task_recurrences(self, rruleobj, dt_start, past=False):
        """Calculates all recurrences of a task given the start
        datetime and a recurrence rule.

        Args:
            rruleobj (dict):   a dict of recurrence rule parameters.
            dt_start (obj): the start datetime.
            past (bool):    include recurrences in the past.

        Returns:
            recurrences (list): a list of datetime objects.

        """
        now = datetime.now(tz=self.ltz)
        rr_freqstr = rruleobj.get('freq')
        frequencies = {
            'MINUTELY': MINUTELY,
            'HOURLY': HOURLY,
            'DAILY': DAILY,
            'WEEKLY': WEEKLY,
            'MONTHLY': MONTHLY,
            'YEARLY': YEARLY
        }
        weekdays = {
            'SU': SU,
            'MO': MO,
            'TU': TU,
            'WE': WE,
            'TH': TH,
            'FR': FR,
            'SA': SA
        }
        if rr_freqstr:
            rr_freqstr = rr_freqstr.upper()
            rr_freq = frequencies.get(rr_freqstr)
        else:
            rr_freq = None
        rr_count = rruleobj.get('count')
        if not rr_count:
            rr_count = self.recurrence_limit
        rr_until = rruleobj.get('until')
        rr_interval = rruleobj.get('interval')
        if not rr_interval:
            rr_interval = 1
        rr_byminute = rruleobj.get('byminute')
        rr_byhour = rruleobj.get('byhour')
        rr_byweekdaystr = rruleobj.get('byweekday')
        if rr_byweekdaystr:
            rr_byweekdaystr = rr_byweekdaystr.upper()
            rr_byweekday = weekdays.get(rr_byweekdaystr)
        else:
            rr_byweekday = None
        rr_bymonth = rruleobj.get('bymonth')
        rr_bymonthday = rruleobj.get('bymonthday')
        rr_byyearday = rruleobj.get('byyearday')
        rr_byweekno = rruleobj.get('byweekno')
        rr_bysetpos = rruleobj.get('bysetpos')
        rr_date = rruleobj.get('date')
        rr_except = rruleobj.get('except')

        if rr_freq:
            all_recurrences = list(rr_rrule(rr_freq,
                                            dtstart=dt_start,
                                            interval=rr_interval,
                                            wkst=self.first_weekday,
                                            count=rr_count,
                                            until=rr_until,
                                            bysetpos=rr_bysetpos,
                                            bymonth=rr_bymonth,
                                            bymonthday=rr_bymonthday,
                                            byyearday=rr_byyearday,
                                            byweekno=rr_byweekno,
                                            byweekday=rr_byweekday,
                                            byhour=rr_byhour,
                                            byminute=rr_byminute))
            # add any specifically defined recurrences
            if rr_date:
                for entry in rr_date:
                    new_dt = self._datetime_or_none(entry)
                    if new_dt:
                        if new_dt not in all_recurrences:
                            all_recurrences.append(new_dt)
            # remove any specifically excluded recurences
            if rr_except:
                for entry in rr_except:
                    new_dt = self._datetime_or_none(entry)
                    if new_dt:
                        if new_dt in all_recurrences:
                            all_recurrences.remove(new_dt)

            all_recurrences.sort()

            if past:
                recurrences = all_recurrences.copy()
            else:
                recurrences = []
                # remove any entries that are in the past
                for entry in all_recurrences:
                    if entry >= now:
                        recurrences.append(entry)
        else:
            recurrences = None

        return recurrences

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (datetime): a valid datetime object or None.

        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.
        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _find_late(self):
        """Build a list of tasks that are overdue to start or finish.

        Returns:
            tasks_late (dict):   a dict of overdue tasks.

        """
        now = datetime.now(tz=self.ltz)
        uids = self._sort_tasks(self.tasks, 'priority')
        tasks_late = {}
        for uid in uids:
            task = self._parse_task(uid)
            is_late = False
            start = task['start']
            due = task['due']
            if start:
                if start.hour == 0 and start.minute == 0:
                    start = start.replace(hour=23, minute=59)
            if due:
                if due.hour == 0 and due.minute == 0:
                    due = due.replace(hour=23, minute=59)
            try:
                if (task['status'] == "todo" and
                        start <= now):
                    is_late = True
            except TypeError:
                pass
            try:
                if (task['status'] not in ["done", "cancelled"] and
                        due <= now):
                    is_late = True
            except TypeError:
                pass
            if is_late:
                tasks_late[uid] = []
        return tasks_late

    def _find_soon(self):
        """Build a list of tasks that start or are due soon.

        Returns:
            tasks_soon (dict):   a dict of tasks starting or due soon.

        """
        now = datetime.now(tz=self.ltz)
        soon = now + timedelta(days=self.days_soon)
        uids = self._sort_tasks(self.tasks, 'priority')
        tasks_soon = {}
        for uid in uids:
            task = self._parse_task(uid)
            is_soon = False
            try:
                if (task['status'] == "todo" and
                        now < task['start'] <= soon):
                    is_soon = True
            except TypeError:
                pass
            try:
                if (task['status'] != "done" and
                        now < task['due'] <= soon):
                    is_soon = True
            except TypeError:
                pass
            if is_soon:
                tasks_soon[uid] = []
        return tasks_soon

    def _find_today(self):
        """Build a list of tasks that start or are due today.

        Returns:
            tasks_today (dict):   a dict of tasks starting or due today.

        """
        now = datetime.now(tz=self.ltz)
        uids = self._sort_tasks(self.tasks, 'priority')
        tasks_today = {}
        for uid in uids:
            task = self._parse_task(uid)
            is_today = False
            try:
                if (task['status'] == "todo" and
                        task['start'].date() == now.date()):
                    is_today = True
            except (AttributeError, TypeError):
                pass
            try:
                if (task['status'] != "done" and
                        task['due'].date() == now.date()):
                    is_today = True
            except (AttributeError, TypeError):
                pass
            if is_today:
                tasks_today[uid] = []
        return tasks_today

    def _format_task(
            self,
            uid,
            subtask=False,
            parent=False,
            project=None):
        """Format task output for a given task.

        Args:
            uid (str):     the uid of the task to format.
            subtask (bool): the task is a subtask in tree view.
            parent (bool): the task is a parent with subtasks.
            project (str): the task is in a project list.

        Returns:
            output (str):   the formatted output.

        """
        task = self._parse_task(uid)

        # primary line
        if task['notes']:
            notesflag = Text("*")
            notesflag.stylize(self.style_flag)
        else:
            notesflag = ""

        if task['rrule'] and task['start']:
            recurflag = Text("@")
            recurflag.stylize(self.style_flag)
        else:
            recurflag = ""

        if task['description']:
            descriptiontxt = Text(task['description'])
            descriptiontxt.stylize(self.style_description)
        else:
            descriptiontxt = ""

        aliastxt = Text(f"({task['alias']}) ")
        aliastxt.stylize(self.style_alias)

        if task['status']:
            statustxt = self._stylize_by_status(
                f"[{task['status'].upper()}] ", task['status'])
        else:
            statustxt = ""

        if task['priority']:
            prioritytxt = self._stylize_by_priority(
                f"[{task['priority']}] ", task['priority'])
        else:
            prioritytxt = ""

        if task['percent']:
            percenttxt = Text(f" ({task['percent']}%)")
            if task['percent'] == 100:
                percenttxt.stylize(self.style_percent_100)
            else:
                percenttxt.stylize(self.style_percent)
        else:
            percenttxt = ""

        # location line
        if task['location']:
            locationlabel = Text("location: ")
            locationlabel.stylize(self.style_label)
            locationfield = Text(task['location'])
            locationfield.stylize(self.style_location)
            locationline = Text.assemble(
                "\n   + ", locationlabel, locationfield)
        else:
            locationline = ""

        # project line
        if task['project'] and not project and not subtask:
            projectlabel = Text("project: ")
            projectlabel.stylize(self.style_label)
            projecttxt = Text(task['project'])
            projecttxt.stylize(self._make_project_style(task['project']))
            projectline = Text.assemble(
                "\n   + ", projectlabel, projecttxt)
        else:
            projectline = ""

        # tag line
        if task['tags']:
            taglabel = Text("tags: ")
            taglabel.stylize(self.style_label)
            tagfield = Text(','.join(task['tags']))
            tagfield.stylize(self.style_tags)
            tagline = Text.assemble(
                "\n   + ", taglabel, tagfield)
        else:
            tagline = ""

        # date line
        now = datetime.now(tz=self.ltz)
        soon = now + timedelta(days=self.days_soon)

        if task['start']:
            startlabel = Text("start: ")
            startlabel.stylize(self.style_label)
            startdate = Text(self._format_timestamp(task['start'], True))
            startdate.stylize(self.style_date)
            if task['status']:
                if task['status'] == "todo":
                    if task['start'] <= now:
                        startdate.stylize(self.style_date_late)
                    elif task['start'] <= soon:
                        startdate.stylize(self.style_date_soon)
            starttxt = Text.assemble(
                    startlabel, startdate, recurflag, "  ")

        else:
            starttxt = ""
        if task['due']:
            duelabel = Text("due: ")
            duelabel.stylize(self.style_label)
            duedate = Text(self._format_timestamp(task['due'], True))
            if task['due'] <= now:
                duedate.stylize(self.style_date_late)
            elif task['due'] <= soon:
                duedate.stylize(self.style_date_soon)
            else:
                duedate.stylize(self.style_date)
            if task['status']:
                if task['status'] == "done":
                    duedate.stylize(self.style_date_done)
            duetxt = Text.assemble(duelabel, duedate, "  ")
        else:
            duetxt = ""
        if task['start'] or task['due']:
            dateline = Text.assemble(
                "\n   + ",
                starttxt,
                duetxt)
        else:
            dateline = ""

        # history line
        if task['started']:
            startedlabel = Text("started: ")
            startedlabel.stylize(self.style_label)
            starteddate = Text(self._format_timestamp(task['started'], True))
            starteddate.stylize(self.style_date)
            startedtxt = Text.assemble(
                startedlabel,
                starteddate,
                "  ")
        else:
            startedtxt = ""
        if task['completed']:
            complabel = Text("completed: ")
            complabel.stylize(self.style_label)
            compdate = Text(self._format_timestamp(task['completed'], True))
            compdate.stylize(self.style_date)
            completedtxt = Text.assemble(complabel, compdate)
        else:
            completedtxt = ""
        if task['started'] or task['completed']:
            historyline = Text.assemble(
                "\n   + ",
                startedtxt,
                completedtxt)
        else:
            historyline = ""

        # parent line (for flat view)
        if task['parent'] and not subtask:
            parentlabel = Text("parent: ")
            parentlabel.stylize(self.style_label)
            parentfield = Text(task['parent'])
            parentfield.stylize(self.style_parent)
            parentline = Text.assemble(
                "\n   + ",
                parentlabel,
                parentfield)
        else:
            parentline = ""

        # subtasks line
        if parent:
            subtaskslabel = Text("subtasks: ")
            subtaskslabel.stylize(self.style_label)
            subtasksline = Text.assemble(
                "\n   + ",
                subtaskslabel)
        else:
            subtasksline = ""

        # assemble lines into task block
        output = Text.assemble(
            "- ",
            aliastxt,
            statustxt,
            prioritytxt,
            descriptiontxt,
            notesflag,
            percenttxt,
            locationline,
            projectline,
            tagline,
            dateline,
            historyline,
            parentline,
            subtasksline)

        return output

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _gen_alias(self):
        """Generates a new alias and check for collisions.

        Returns:
            alias (str):    a randomly-generated alias.

        """
        aliases = self._get_aliases()
        chars = string.ascii_lowercase + string.digits
        while True:
            alias = ''.join(random.choice(chars) for x in range(4))
            if alias not in aliases:
                break
        return alias

    def _get_aliases(self):
        """Generates a list of all task aliases.

        Returns:
            aliases (list): the list of all task aliases.

        """
        aliases = []
        for task in self.tasks:
            alias = self.tasks[task].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    @staticmethod
    def _integer_or_default(inputdata, default=None):
        """Verify an input data and return an integer or a default
        value (or None).

        Args:
            inputdata (str): a string or number.
            default (int or None):  a default to use if there is an
        exception.

        Returns:
            output (int): a verified integer, a default value, or None.

        """
        try:
            output = int(inputdata)
        except (ValueError, TypeError):
            output = default
        return output

    def _make_parents(self):
        self.parents = {}
        for task in self.tasks:
            parent = self.tasks[task].get('parent')
            if parent:
                # get the uid matching the parent's alias
                uid = None
                for this_task in self.tasks:
                    alias = self.tasks[this_task].get('alias')
                    if alias == parent:
                        uid = this_task
                if uid:
                    if uid in self.parents.keys():
                        self.parents[uid].append(task)
                    else:
                        children = [task]
                        self.parents[uid] = children

    def _make_project_style(self, project):
        """Create a style for a project label based on values in
        self.project_colors.

        Args:
            project (str): the project name to stylize.\

        Returns:
            this_style (obj): Rich Style() object.

        """
        color = self.project_colors.get(project)
        if color and self.color_enabled:
            try:
                this_style = Style(color=color)
            except ColorParseError:
                this_style = Style(color="default")
        else:
            this_style = Style(color="default")

        return this_style

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))
                # warning days for upcoming tasks
                self.days_soon = config["main"].get(
                    "days_soon", 1)
                # user email for notifications
                self.user_email = config["main"].get("user_email")
                # default notification duration
                if config["main"].get("default_duration"):
                    try:
                        self.default_duration = int(
                                config["main"].get("default_duration"))
                    except ValueError:
                        self.default_duration = DEFAULT_DURATION
                # default reminder expression
                if config["main"].get("default_reminder"):
                    self.default_reminder = (
                            config["main"].get("default_reminder",
                                               DEFAULT_REMINDER))
                # default first day of the week (for calculating rrules)
                if config["main"].get("first_weekday"):
                    try:
                        self.first_weekday = int(
                                config["main"].get("first_weekday"))
                    except ValueError:
                        self.first_weekday = DEFAULT_FIRST_WEEKDAY
                # priority thresholds
                self.priority_high = config["main"].get(
                    "priority_high", 3)
                self.priority_medium = config["main"].get(
                    "priority_medium", 6)
                self.priority_normal = config["main"].get(
                    "priority_normal", 9)
                try:
                    self.days_soon = int(self.days_soon)
                except (ValueError, TypeError):
                    print(
                        "NOTICE: invalid config option 'days_soon', "
                        "defaulting to 1."
                    )
                    self.days_soon = 1
                try:
                    self.priority_high = int(self.priority_high)
                except (ValueError, TypeError):
                    print(
                        "NOTICE: invalid config option 'priority_high',"
                        " defaulting to 3."
                    )
                    self.priority_high = 3
                try:
                    self.priority_medium = int(self.priority_medium)
                except (ValueError, TypeError):
                    print(
                        "NOTICE: invalid config option "
                        "'priority_medium', defaulting to 6."
                    )
                    self.priority_medium = 6
                try:
                    self.priority_normal = int(self.priority_normal)
                except (ValueError, TypeError):
                    print(
                        "NOTICE: invalid config option "
                        "'priority_normal', defaulting to 9."
                    )
                    self.priority_normal = 9

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.
                """
                try:
                    self.style_title = Style(
                        color=self.color_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_description = Style(
                        color=self.color_description)
                except ColorParseError:
                    pass
                try:
                    self.style_location = Style(
                        color=self.color_location)
                except ColorParseError:
                    pass
                try:
                    self.style_alias = Style(
                        color=self.color_alias)
                except ColorParseError:
                    pass
                try:
                    self.style_tags = Style(
                        color=self.color_tags)
                except ColorParseError:
                    pass
                try:
                    self.style_parent = Style(
                        color=self.color_parent)
                except ColorParseError:
                    pass
                try:
                    self.style_label = Style(
                        color=self.color_label)
                except ColorParseError:
                    pass
                try:
                    self.style_date = Style(
                        color=self.color_date)
                except ColorParseError:
                    pass
                try:
                    self.style_date_soon = Style(
                        color=self.color_date_soon,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_date_late = Style(
                        color=self.color_date_late,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_done = Style(
                        color=self.color_status_done,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_todo = Style(
                        color=self.color_status_todo,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_inprogress = Style(
                        color=self.color_status_inprogress,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_waiting = Style(
                        color=self.color_status_waiting,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_onhold = Style(
                        color=self.color_status_onhold,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_blocked = Style(
                        color=self.color_status_blocked,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_cancelled = Style(
                        color=self.color_status_cancelled,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_status_default = Style(
                        color="default",
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_priority_low = Style(
                        color=self.color_priority_low)
                except ColorParseError:
                    pass
                try:
                    self.style_priority_normal = Style(
                        color=self.color_priority_normal)
                except ColorParseError:
                    pass
                try:
                    self.style_priority_medium = Style(
                        color=self.color_priority_medium)
                except ColorParseError:
                    pass
                try:
                    self.style_priority_high = Style(
                        color=self.color_priority_high)
                except ColorParseError:
                    pass
                try:
                    self.style_percent = Style(
                        color=self.color_percent)
                except ColorParseError:
                    pass
                try:
                    self.style_percent_100 = Style(
                        color=self.color_percent_100,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_flag = Style(
                        color=self.color_flag,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_date_done = Style(
                        color=self.color_date,
                        bold=False)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors
                self.color_title = (
                    config["colors"].get(
                        "title", "bright_blue"))
                self.color_description = (
                    config["colors"].get(
                        "description", "default"))
                self.color_location = (
                    config["colors"].get(
                        "location", "default"))
                self.color_alias = (
                    config["colors"].get(
                        "alias", "bright_black"))
                self.color_tags = (
                    config["colors"].get(
                        "tags", "cyan"))
                self.color_parent = (
                    config["colors"].get(
                        "parent", "cyan"))
                self.color_label = (
                    config["colors"].get(
                        "label", "white"))
                self.color_date = (
                    config["colors"].get(
                        "date", "green"))
                self.color_date_soon = (
                    config["colors"].get(
                        "date_soon", "yellow"))
                self.color_date_late = (
                    config["colors"].get(
                        "date_late", "red"))
                self.color_status_done = (
                    config["colors"].get(
                        "status_done", "green"))
                self.color_status_todo = (
                    config["colors"].get(
                        "status_todo", "red"))
                self.color_status_inprogress = (
                    config["colors"].get(
                        "status_inprogress", "cyan"))
                self.color_status_waiting = (
                    config["colors"].get(
                        "status_waiting", "magenta"))
                self.color_status_onhold = (
                    config["colors"].get(
                        "status_onhold", "blue"))
                self.color_status_blocked = (
                    config["colors"].get(
                        "status_blocked", "yellow"))
                self.color_status_cancelled = (
                    config["colors"].get(
                        "status_cancelled", "bright_black"))
                self.color_priority_low = (
                    config["colors"].get(
                        "priority_low", "bright_blue"))
                self.color_priority_normal = (
                    config["colors"].get(
                        "priority_normal", "bright_green"))
                self.color_priority_medium = (
                    config["colors"].get(
                        "priority_medium", "bright_yellow"))
                self.color_priority_high = (
                    config["colors"].get(
                        "priority_high", "bright_red"))
                self.color_percent = (
                    config["colors"].get(
                        "percent", "cyan"))
                self.color_percent_100 = (
                    config["colors"].get(
                        "percent_100", "bright_cyan"))
                self.color_flag = (
                    config["colors"].get(
                        "flag", "bright_yellow"))

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_enabled = False
                    self.color_title = "default"
                    self.color_description = "default"
                    self.color_location = "default"
                    self.color_alias = "default"
                    self.color_tags = "default"
                    self.color_parent = "default"
                    self.color_label = "default"
                    self.color_date = "default"
                    self.color_date_soon = "default"
                    self.color_date_late = "default"
                    self.color_status_done = "default"
                    self.color_status_todo = "default"
                    self.color_status_inprogress = "default"
                    self.color_status_waiting = "default"
                    self.color_status_onhold = "default"
                    self.color_status_blocked = "default"
                    self.color_status_cancelled = "default"
                    self.color_priority_low = "default"
                    self.color_priority_normal = "default"
                    self.color_priority_medium = "default"
                    self.color_priority_high = "default"
                    self.color_percent = "default"
                    self.color_percent_100 = "default"
                    self.color_flag = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # try to apply requested custom colors
                _apply_colors()

            if "project_colors" in config:
                project_colors = config["project_colors"]
                self.project_colors = {}
                for proj in project_colors:
                    self.project_colors[proj] = project_colors.get(proj)
        else:
            self._error_exit("Config file not found")

    def _parse_files(self):
        """ Read task files from `data_dir` and parse task data into
        `tasks`.

        Returns:
            tasks (dict):    parsed data from each task file

        """
        this_task_files = {}
        this_tasks = {}
        aliases = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                if entry.name.endswith('.yml') and entry.is_file():
                    fullpath = entry.path
                    data = None
                    try:
                        with open(fullpath, "r",
                                  encoding="utf-8") as entry_file:
                            data = yaml.safe_load(entry_file)
                    except (OSError, IOError, yaml.YAMLError):
                        self._error_pass(
                            f"failure reading or parsing {fullpath} "
                            "- SKIPPING")
                    if data:
                        uid = None
                        task = data.get("task")
                        if task:
                            uid = task.get("uid")
                            alias = task.get("alias")
                            add_task = True
                            if uid:
                                # duplicate UID detection
                                dupid = this_task_files.get(uid)
                                if dupid:
                                    self._error_pass(
                                        "duplicate UID detected:\n"
                                        f"  {uid}\n"
                                        f"  {dupid}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_task = False
                            if alias:
                                # duplicate alias detection
                                dupalias = aliases.get(alias)
                                if dupalias:
                                    self._error_pass(
                                        "duplicate alias detected:\n"
                                        f"  {alias}\n"
                                        f"  {dupalias}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_task = False
                            if add_task:
                                if alias and uid:
                                    this_tasks[uid] = task
                                    this_task_files[uid] = fullpath
                                    aliases[alias] = fullpath
                                else:
                                    self._error_pass(
                                        "no uid and/or alias param "
                                        f"in {fullpath} - SKIPPING")
                        else:
                            self._error_pass(
                                f"no data in {fullpath} - SKIPPING")
        self.tasks = this_tasks.copy()
        self.task_files = this_task_files.copy()
        self._make_parents()

    def _parse_rrule(self, expression):
        """Parses a recurring rule expression and returns a dict of
        recurrence parameters.

        Args:
            expression (str):   the rrule expression.

        Returns:
            rrule (dict):       the recurrence parameters (or None)

        """
        expression = expression.lower()
        valid_criteria = [
                "date=",        # specific recurrence dates
                "except=",      # specific exception dates
                "freq=",        # frequency (minutely, hourly, daily,
                                #   weekly, monthly, yearly)
                "count=",       # number of recurrences
                "until=",       # recur until date
                "interval=",    # interval of recurrence
                "byhour=",      # recur by hour (0-23)
                "byweekday=",   # SU, MO, TU, WE, TH, FR, SA
                "bymonth=",     # recur by month (1-12)
                "bymonthday=",  # day of month (1-31)
                "byyearday=",   # day of the year (1-366)
                "byweekno=",    # week of year (1-53)
                "bysetpos=",    # set position of occurence set (e.g.,
                                # 1 for first, -1 for last, -2 for
                                # second to last
        ]
        if not any(x in expression for x in valid_criteria):
            rrule = None
        else:
            try:
                rrule = dict((k.strip(), v.strip())
                             for k, v in (item.split('=')
                             for item in expression.split(';')))
            except ValueError:
                rrule = None

        if rrule.get('date'):
            date_strings = rrule['date'].split(',')
            rr_date = []
            for entry in date_strings:
                this_date = self._datetime_or_none(entry)
                if this_date:
                    rr_date.append(this_date)
            rrule['date'] = sorted(rr_date)

        if rrule.get('except'):
            except_strings = rrule['except'].split(',')
            rr_except = []
            for entry in except_strings:
                this_except = self._datetime_or_none(entry)
                if this_except:
                    rr_except.append(this_except)
            rrule['except'] = sorted(rr_except)

        if rrule.get('freq'):
            rr_freq = rrule['freq'].upper()
            if rr_freq in ['MINUTELY', 'HOURLY', 'DAILY',
                           'WEEKLY', 'MONTHLY', 'YEARLY']:
                rrule['freq'] = rr_freq
            else:
                rrule['freq'] = None

        if rrule.get('count'):
            rrule['count'] = self._integer_or_default(rrule['count'])

        if rrule.get('until'):
            rrule['until'] = self._datetime_or_none(rrule['until'])

        if rrule.get('interval'):
            rrule['interval'] = self._integer_or_default(rrule['interval'])

        if rrule.get('byhour'):
            rr_byhour = self._integer_or_default(rrule['byhour'])
            if rr_byhour:
                if 0 <= rr_byhour <= 23:
                    rrule['byhour'] = rr_byhour
                else:
                    rrule['byhour'] = None
            else:
                rrule['byhour'] = None

        if rrule.get('byweekday'):
            rr_byweekday = rrule['byweekday'].upper()
            if rr_byweekday in ['SU', 'MO', 'TU', 'WE',
                                'TH', 'FR', 'SA']:
                rrule['byweekday'] = rr_byweekday
            else:
                rrule['byweekday'] = None

        if rrule.get('bymonth'):
            rr_bymonth = self._integer_or_default(rrule['bymonth'])
            if rr_bymonth:
                if 1 <= rr_bymonth <= 12:
                    rrule['bymonth'] = rr_bymonth
                else:
                    rrule['bymonth'] = None
            else:
                rrule['bymonth'] = None

        if rrule.get('bymonthday'):
            rr_bymonthday = self._integer_or_default(rrule['bymonthday'])
            if rr_bymonthday:
                if 1 <= rr_bymonthday <= 31:
                    rrule['bymonthday'] = rr_bymonthday
                else:
                    rrule['bymonthday'] = None
            else:
                rrule['bymonthday'] = None

        if rrule.get('byyearday'):
            rr_byyearday = self._integer_or_default(rrule['byyearday'])
            if rr_byyearday:
                if 1 <= rr_byyearday <= 366:
                    rrule['byyearday'] = rr_byyearday
                else:
                    rrule['byyearday'] = None
            else:
                rrule['byyearday'] = None

        if rrule.get('byweekno'):
            rr_byweekno = self._integer_or_default(rrule['byweekno'])
            if rr_byweekno:
                if 1 <= rr_byweekno <= 53:
                    rrule['byweekno'] = rr_byweekno
                else:
                    rrule['byweekno'] = None
            else:
                rrule['byweekno'] = None

        if rrule.get('bysetpos'):
            rrule['bysetpos'] = self._integer_or_default(rrule['bysetpos'])

        return rrule

    def _parse_task(self, uid):
        """Parse a task and return values for task parameters.

        Args:
            uid (str): the UUID of the task to parse.

        Returns:
            task (dict):    the task parameters.

        """
        task = {}
        task['uid'] = self.tasks[uid].get('uid')

        task['created'] = self.tasks[uid].get('created')
        if task['created']:
            task['created'] = self._datetime_or_none(task['created'])

        task['updated'] = self.tasks[uid].get('updated')
        if task['updated']:
            task['updated'] = self._datetime_or_none(task['updated'])

        task['alias'] = self.tasks[uid].get('alias')
        if task['alias']:
            task['alias'] = task['alias'].lower()

        task['description'] = self.tasks[uid].get('description')
        task['location'] = self.tasks[uid].get('location')

        task['project'] = self.tasks[uid].get('project')
        if task['project']:
            task['project'] = task['project'].lower()

        task['rrule'] = self.tasks[uid].get('rrule')

        task['priority'] = self.tasks[uid].get('priority')
        if task['priority']:
            task['priority'] = self._integer_or_default(task['priority'])

        task['tags'] = self.tasks[uid].get('tags')

        task['start'] = self.tasks[uid].get('start')
        if task['start']:
            task['start'] = self._datetime_or_none(task['start'])

        task['due'] = self.tasks[uid].get('due')
        if task['due']:
            task['due'] = self._datetime_or_none(task['due'])

        task['started'] = self.tasks[uid].get('started')
        if task['started']:
            task['started'] = self._datetime_or_none(task['started'])

        task['completed'] = self.tasks[uid].get('completed')
        if task['completed']:
            task['completed'] = self._datetime_or_none(task['completed'])

        task['percent'] = self.tasks[uid].get('percent')
        if task['percent']:
            task['percent'] = self._integer_or_default(task['percent'])

        task['status'] = self.tasks[uid].get('status')
        if task['status']:
            task['status'] = task['status'].lower()

        task['parent'] = self.tasks[uid].get('parent')
        if task['parent']:
            task['parent'] = task['parent'].lower()

        task['reminders'] = self.tasks[uid].get('reminders')

        task['notes'] = self.tasks[uid].get('notes')

        return task

    @staticmethod
    def _pass_filter(condition, status):
        """Check a provided status against a predefined condition and
        return True or False if the status passes the filter.

        Args:
            condition (str):    the condition profile.
            status (str):       the task status to check.

        Returns:
            passes (bool):       whether or not the status passes the
        filter.

        """
        if not status:
            # no status, can't meet any condition
            passes = False
        elif condition == 'done':
            passes = status.lower() == 'done'
        elif condition == 'open':
            passes = status.lower() not in ['done', 'cancelled']
        else:
            # no filter / not a valid filter, everything passes
            passes = True

        return passes

    def _perform_search(self, term):
        """Parses a search term and returns a list of matching tasks.
        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a task record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a task record.

        Args:
            term (str):     the search term to parse.

        Returns:
            this_tasks (list):   the tasks matching the search criteria.

        """
        # helper lambda functions for parsing search and exclude strings
        def _parse_dt_range(timestr):
            """Parses a datetime range expression and returns start and
            end datetime objects.

            Args:
                timestr (str):  the datetime range string provided.

            Returns:
                begin (obj):    a valid datetime object.
                end (obj):      a valid datetime object.

            """
            now = datetime.now(tz=self.ltz)
            origin = datetime(1969, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            if timestr.startswith("~"):
                begin = origin
                end = self._datetime_or_none(
                          timestr.replace("~", ""))
            elif timestr.endswith("~"):
                begin = self._datetime_or_none(
                            timestr.replace("~", ""))
                end = now
            elif "~" in timestr:
                times = timestr.split("~")
                begin = self._datetime_or_none(
                            times[0].strip())
                end = self._datetime_or_none(
                            times[1].strip())
            else:
                begin = self._datetime_or_none(timestr)
                end = self._datetime_or_none(timestr)
            # return a valid range, regardless
            # if the input values were bad, we'll just ignore them and
            # match all timestamps 1969-01-01 to present.
            if not begin:
                begin = origin
            if not end:
                end = now
            # in the case that an end date was provided without a time,
            # set the time to the last second of the date to match any
            # time in that day.
            elif end.hour == 0 and end.minute == 0:
                end = end.replace(hour=23, minute=59, second=59)
            return begin, end

        def _parse_pri_range(prioritystr):
            """Parses a priority range expression and returns start and
            end integers.

            Args:
                prioritystr (str):  the priority range string provided.

            Returns:
                begin (int):    the beginning integer value.
                end (int):      the end integer value.

            """
            # ensure we start with a string
            prioritystr = str(prioritystr)
            if prioritystr.startswith('~'):
                begin = 1
                end = self._integer_or_default(
                          prioritystr.replace('~', ''))
            elif prioritystr.endswith('~'):
                begin = self._integer_or_default(
                            prioritystr.replace('~', ''))
                end = 1000
            elif '~' in prioritystr:
                prange = prioritystr.split('~')
                prange.sort()
                begin = self._integer_or_default(prange[0])
                end = self._integer_or_default(prange[1])
            else:
                begin = self._integer_or_default(prioritystr)
                end = self._integer_or_default(prioritystr)
            if not begin:
                begin = 1
            if not end:
                end = 1000
            return begin, end

        def _parse_perc_range(percentstr):
            """Parses a percent range expression and returns start and
            end integers.

            Args:
                percentstr (str):  the percent range string provided.

            Returns:
                begin (int):    the beginning integer value.
                end (int):      the end integer value.

            """
            # ensure we start with a string
            percentstr = str(percentstr)
            if percentstr.startswith('~'):
                begin = 0
                end = self._integer_or_default(
                          percentstr.replace('~', ''))
            elif percentstr.endswith('~'):
                begin = self._integer_or_default(
                            percentstr.replace('~', ''))
                end = 100
            elif '~' in percentstr:
                prange = percentstr.split('~')
                prange.sort()
                begin = self._integer_or_default(prange[0])
                end = self._integer_or_default(prange[1])
            else:
                begin = self._integer_or_default(percentstr)
                end = self._integer_or_default(percentstr)
            if not begin:
                begin = 0
            if not end:
                end = 100
            return begin, end

        # if the exclusion operator is in the provided search term then
        # split the term into two components: search and exclude
        # otherwise, treat it as just a search term alone.
        if "%" in term:
            term = term.split("%")
            searchterm = str(term[0]).lower()
            excludeterm = str(term[1]).lower()
        else:
            searchterm = str(term).lower()
            excludeterm = None

        valid_criteria = [
            "uid=",
            "description=",
            "location=",
            "project=",
            "alias=",
            "tags=",
            "status=",
            "parent=",
            "priority=",
            "percent=",
            "start=",
            "due=",
            "started=",
            "completed=",
            "notes="
        ]
        # parse the search term into a dict
        if searchterm:
            if searchterm == 'any':
                search = None
            elif not any(x in searchterm for x in valid_criteria):
                # treat this as a simple description search
                search = {}
                search['description'] = searchterm.strip()
            else:
                try:
                    search = dict((k.strip(), v.strip())
                                  for k, v in (item.split('=')
                                  for item in searchterm.split(',')))
                except ValueError:
                    msg = "invalid search expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            search = None

        # parse the exclude term into a dict
        if excludeterm:
            if not any(x in excludeterm for x in valid_criteria):
                # treat this as a simple description search
                exclude = {}
                exclude['description'] = excludeterm.strip()
            else:
                try:
                    exclude = dict((k.strip(), v.strip())
                                   for k, v in (item.split('=')
                                   for item in excludeterm.split(',')))
                except ValueError:
                    msg = "invalid exclude expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            exclude = None

        this_tasks = {}
        for uid in self.tasks:
            this_tasks[uid] = []
        exclude_list = []

        if exclude:
            x_uid = exclude.get('uid')
            x_alias = exclude.get('alias')
            x_description = exclude.get('description')
            x_location = exclude.get('location')
            x_project = exclude.get('project')
            x_tags = exclude.get('tags')
            if x_tags:
                x_tags = x_tags.split('+')
            x_status = exclude.get('status')
            if x_status:
                x_status = x_status.split('+')
            x_parent = exclude.get('parent')
            x_priority = exclude.get('priority')
            x_percent = exclude.get('percent')
            x_start = exclude.get('start')
            x_due = exclude.get('due')
            x_started = exclude.get('started')
            x_completed = exclude.get('completed')
            x_notes = exclude.get('notes')

            for uid in this_tasks:
                task = self._parse_task(uid)
                remove = False
                if x_uid:
                    if x_uid == uid:
                        remove = True
                if x_alias:
                    if task['alias']:
                        if x_alias == task['alias']:
                            remove = True
                if x_description:
                    if task['description']:
                        if x_description in task['description']:
                            remove = True
                if x_location:
                    if task['location']:
                        if x_location in task['location']:
                            remove = True
                if x_project:
                    if task['project']:
                        if x_project in task['project']:
                            remove = True
                if x_tags:
                    if task['tags']:
                        for tag in x_tags:
                            if tag in task['tags']:
                                remove = True
                if x_status:
                    if task['status']:
                        for this_status in x_status:
                            if this_status == task['status']:
                                remove = True
                if x_parent:
                    if task['parent']:
                        if x_parent == task['parent']:
                            remove = True
                if x_priority:
                    if task['priority']:
                        begin, end = _parse_pri_range(x_priority)
                        if begin <= task['priority'] <= end:
                            remove = True
                if x_percent:
                    if task['percent']:
                        begin, end = _parse_perc_range(x_percent)
                        if begin <= task['percent'] <= end:
                            remove = True
                if x_start:
                    if task['start']:
                        begin, end = _parse_dt_range(x_start)
                        if begin <= task['start'] <= end:
                            remove = True
                if x_due:
                    if task['due']:
                        begin, end = _parse_dt_range(x_due)
                        if begin <= task['due'] <= end:
                            remove = True
                if x_started:
                    if task['started']:
                        begin, end = _parse_dt_range(x_started)
                        if begin <= task['started'] <= end:
                            remove = True
                if x_completed:
                    if task['completed']:
                        begin, end = _parse_dt_range(x_completed)
                        if begin <= task['completed'] <= end:
                            remove = True
                if x_notes:
                    if task['notes']:
                        if x_notes in task['notes']:
                            remove = True

                if remove:
                    exclude_list.append(uid)

        # remove excluded tasks
        for uid in exclude_list:
            this_tasks.pop(uid)

        not_match = []

        if search:
            s_uid = search.get('uid')
            s_alias = search.get('alias')
            s_description = search.get('description')
            s_location = search.get('location')
            s_project = search.get('project')
            s_tags = search.get('tags')
            if s_tags:
                s_tags = s_tags.split('+')
            s_status = search.get('status')
            if s_status:
                s_status = s_status.split('+')
            s_parent = search.get('parent')
            s_priority = search.get('priority')
            s_percent = search.get('percent')
            s_start = search.get('start')
            s_due = search.get('due')
            s_started = search.get('started')
            s_completed = search.get('completed')
            s_notes = search.get('notes')
            if s_notes:
                s_notes = s_notes.lower()

            for uid in this_tasks:
                task = self._parse_task(uid)
                remove = False
                if s_uid:
                    if not s_uid == uid:
                        remove = True
                if s_alias:
                    if task['alias']:
                        if not s_alias == task['alias']:
                            remove = True
                    else:
                        remove = True
                if s_description:
                    if task['description']:
                        if (s_description not in
                                task['description'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_location:
                    if task['location']:
                        if (s_location not in
                                task['location'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_project:
                    if task['project']:
                        if (s_project not in
                                task['project'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_tags:
                    keep = False
                    if task['tags']:
                        # searching for tags allows use of the '+' OR
                        # operator, so if we match any tag in the list
                        # then keep the entry
                        for tag in s_tags:
                            if tag in task['tags']:
                                keep = True
                    if not keep:
                        remove = True
                if s_status:
                    keep = False
                    if task['status']:
                        # searching for status allows use of the '+' OR
                        # operator, so if we match any status in the
                        # list then keep the entry
                        for this_status in s_status:
                            if this_status == task['status']:
                                keep = True
                    if not keep:
                        remove = True
                if s_parent:
                    if task['parent']:
                        if s_parent != task['parent']:
                            remove = True
                    else:
                        remove = True
                if s_priority:
                    if task['priority']:
                        begin, end = _parse_pri_range(s_priority)
                        if not begin <= task['priority'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_percent:
                    if task['percent']:
                        begin, end = _parse_perc_range(s_percent)
                        if not begin <= task['percent'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_start:
                    if task['start']:
                        begin, end = _parse_dt_range(s_start)
                        if not begin <= task['start'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_due:
                    if task['due']:
                        begin, end = _parse_dt_range(s_due)
                        if not begin <= task['due'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_started:
                    if task['started']:
                        begin, end = _parse_dt_range(s_started)
                        if not begin <= task['started'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_completed:
                    if task['completed']:
                        begin, end = _parse_dt_range(s_completed)
                        if not begin <= task['completed'] <= end:
                            remove = True
                    else:
                        remove = True
                if s_notes:
                    if task['notes']:
                        if s_notes not in task['notes'].lower():
                            remove = True
                    else:
                        remove = True
                if remove:
                    not_match.append(uid)

        # remove the tasks that didn't match search criteria
        for uid in not_match:
            this_tasks.pop(uid)

        return this_tasks

    def _print_task_list(self, tasks, view, pager=False, project=None):
        """Print the formatted task list.

        Args:
            tasks (dict):   the dict of tasks (and subtasks) to be
        printed in a formatted manner.
            view (str):     the view to display (e.g., open, all, etc.)
            pager (bool):   whether or not to page output (default no).
            project (str):  filter the list by project.

        """
        console = Console()
        if project:
            title = f"Tasks - {view} ({project})"
        else:
            title = f"Tasks - {view}"
        # table
        task_table = Table(
            title=title,
            title_style=self.style_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            padding=(0, 0, 0, 0))
        # single column
        task_table.add_column("column1")
        # task list/tree
        if tasks:
            for task in tasks:
                if tasks[task]:
                    ftask = self._format_task(
                        task,
                        parent=True,
                        project=project)
                    task_table.add_row(ftask)
                    subtask_table = Table(
                        title=None,
                        box=None,
                        show_header=False,
                        show_lines=False,
                        pad_edge=True,
                        collapse_padding=False,
                        padding=(0, 0, 0, 4))
                    for subtask in tasks[task]:
                        fsubtask = self._format_task(subtask, subtask=True)
                        subtask_table.add_row(fsubtask)
                    task_table.add_row(subtask_table)
                else:
                    ftask = self._format_task(task)
                    task_table.add_row(ftask)
                task_table.add_row("")
        else:
            task_table.add_row(f"None{' '*21}")
        # single-column layout
        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(task_table)

        # render the output with a pager if -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _sort_tasks(self, tasks, sortby, reverse=False):
        """Sort a list of tasks by a parameter and return a sorted dict.

        Args:
            tasks (list):   the tasks to sort.
            sortby (str):   the parameter by which to sort.
            reverse (bool): sort in reverse (optional).

        Returns:
            uids (dict):    a sorted dict of tasks.

        """
        fifouids = {}
        for uid in tasks:
            sort = self.tasks[uid].get(sortby)
            if sort and sortby == 'priority':
                sort = self._integer_or_default(sort, 1000)
            if sort and sortby == 'percent':
                sort = self._integer_or_default(sort, 0)
            if not sort:
                if sortby == 'priority':
                    sort = 1000
                elif sortby == 'percent':
                    sort = 0
                else:
                    sort = ""
            fifouids[uid] = sort
        sortlist = sorted(
            fifouids.items(), key=lambda x: x[1], reverse=reverse
        )
        uids = dict(sortlist)
        return uids

    def _stylize_by_status(self, textstr, status):
        """Stylize a text string based on the task status and return a
        rich.Text() object stylized appropriately.

        Args:
            textstr (str):  the string to stylize.
            status (str):   the task status.

        Returns:
            styled (obj):   the stylized Text() object.

        """
        status = status.lower()
        styled = Text(textstr)

        if status == "done":
            styled.stylize(self.style_status_done)
        elif status == "todo":
            styled.stylize(self.style_status_todo)
        elif status == "inprogress":
            styled.stylize(self.style_status_inprogress)
        elif status == "waiting":
            styled.stylize(self.style_status_waiting)
        elif status == "onhold":
            styled.stylize(self.style_status_onhold)
        elif status == "blocked":
            styled.stylize(self.style_status_blocked)
        elif status == "cancelled":
            styled.stylize(self.style_status_cancelled)
        else:
            styled.stylize(self.style_status_default)

        return styled

    def _stylize_by_priority(self, textstr, priority):
        """Stylize a text string based on the task priority and return a
        rich.Text() object stylized appropriately.

        Args:
            textstr (str):  the string to stylize.
            priority (str):   the task priority.

        Returns:
            styled (obj):   the stylized Text() object.

        """
        styled = Text(textstr)

        if priority <= self.priority_high:
            styled.stylize(self.style_priority_high)
        elif priority <= self.priority_medium:
            styled.stylize(self.style_priority_medium)
        elif priority <= self.priority_normal:
            styled.stylize(self.style_priority_normal)
        else:
            styled.stylize(self.style_priority_low)

        return styled

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the task for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for task in self.tasks:
            this_alias = self.tasks[task].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = task
        return uid

    def _verify_data_dir(self):
        """Create the tasks data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created")
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    @staticmethod
    def _write_yaml_file(data, filename):
        """Write YAML data to a file.

        Args:
            data (dict):    the structured data to write.
            filename (str): the location to write the data.

        """
        with open(filename, "w",
                  encoding="utf-8") as out_file:
            yaml.dump(
                data,
                out_file,
                default_flow_style=False,
                sort_keys=False)

    def add_another_reminder(self):
        """Asks if the user wants to add another reminder."""
        another = input("Add another reminder? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_reminder()

    def add_confirm_reminder(
            self,
            remind,
            notify,
            another=True):
        """Confirms the reminder expression provided.

        Args:
            remind (str):   the reminder date or expression.
            notify (int):   1 (display) or 2 (email)
            another (bool): offer to add another when complete.

        """
        if not remind:
            self._error_pass("reminder date/expression "
                             "cannot be empty")
            self.add_new_reminder(another)
        else:
            if notify == 2:
                notify = 'email'
            else:
                notify = 'display'
            print(
                "\n"
                "  New reminder:\n"
                f"    dt/expr: {remind}\n"
                f"    notify by: {notify}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [remind, notify]
                if not self.add_reminders:
                    self.add_reminders = []
                self.add_reminders.append(data)
                if another:
                    self.add_another_reminder()
            else:
                self.add_new_reminder(another)

    def add_new_reminder(self, another=True):
        """Prompts the user through adding a new task reminder.

        Args:
            another (bool): offer to add another when complete.

        """
        remind = input("Reminder date/time or expression? "
                       "[default]: ") or self.default_reminder
        notify = input("Notify by (1) display, "
                       "or (2) email [1]: ") or 1
        try:
            notify = int(notify)
        except ValueError:
            notify = 1
        if notify not in [1, 2]:
            notify = 1
        self.add_confirm_reminder(remind, notify, another)

    def archive(self, alias, force=False):
        """Archive a task identified by alias. Move the task to the
        {data_dir}/archive directory.

        Args:
            alias (str):    The alias of the task to be archived.
            force (bool):   Don't ask for confirmation before archiving.

        """
        def _move_file(uid, archive_dir, ignore=False):
            """Moves a task file to the archive directory.

            Args:
                uid (str):  the UID of the task to archive.
                archive_dir (str): the archive directory path.
                ignore (bool): ignore errors and continue.

            Returns:
                success (bool): the move operation succeeded.

            """
            filename = self.task_files.get(uid)
            if filename:
                archive_file = os.path.join(
                    archive_dir, os.path.basename(filename))
                try:
                    shutil.move(filename, archive_file)
                except IOError:
                    msg = f"failure moving {filename}"
                    if ignore:
                        self._error_pass(msg)
                        success = False
                    else:
                        self._handle_error(msg)
                        success = False
                else:
                    success = True
            else:
                msg = f"failed to find file for {uid}"
                if ignore:
                    self._error_pass(msg)
                    success = False
                else:
                    self._handle_error(msg)
                    success = False
            return success

        archive_dir = os.path.join(self.data_dir, "archive")
        if not os.path.exists(archive_dir):
            try:
                os.makedirs(archive_dir)
            except IOError:
                msg = (
                    f"{archive_dir} doesn't exist and can't be created"
                )
                if not self.interactive:
                    self._error_exit(msg)
                else:
                    self._error_pass(msg)
                    return

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Archive {alias} and all subtasks "
                                "(if any)? [N/y]: ").lower()
            if confirm in ['yes', 'y']:
                # if we fail on archiving a parent task, don't try to
                # archive children. if we fail on archiving a child task
                # continue trying to archive the remaining tasks.
                msg = f"Archived task: {alias}"
                result = _move_file(uid, archive_dir)
                if result and uid in self.parents:
                    subtasks = self.parents[uid]
                    for task in subtasks:
                        _move_file(task, archive_dir, ignore=True)
                    print(msg)
                elif result:
                    print(msg)
            else:
                print("Cancelled.")

    def complete(self, alias):
        """Mark as task as completed, update status and completed date.

        Args:
            alias (str):    the alias of the task to complete.

        """
        now = datetime.now(tz=self.ltz)
        self.modify(
            alias=alias,
            new_completed=now,
            new_percent=100,
            new_status='done')

    def delete(self, alias, force=False):
        """Delete a task identified by alias.

        Args:
            alias (str):    The alias of the task to be deleted.

        """
        def _remove_file(uid, ignore=False):
            """Deletes a task file.

            Args:
                uid (str):  the UID of the task to delete.
                ignore (bool): ignore errors and continue.

            Returns:
                success (bool): the operation succeeded.

            """
            filename = self.task_files.get(uid)
            if filename:
                try:
                    os.remove(filename)
                except OSError:
                    msg = f"failure deleting {filename}"
                    if ignore:
                        self._error_pass(msg)
                        success = False
                    else:
                        self._handle_error(msg)
                        success = False
                else:
                    success = True
            else:
                msg = f"failed to find file for {uid}"
                if ignore:
                    self._error_pass(msg)
                    success = False
                else:
                    self._handle_error(msg)
                    success = False
            return success

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Delete '{alias}' and all subtasks "
                                "(if any)? [yes/no]: ").lower()
            if confirm in ['yes', 'y']:
                # if we fail on removing a parent task, don't try to
                # remove children. if we fail on removing a child task
                # continue trying to remove the remaining tasks.
                msg = f"Deleted task: {alias}"
                result = _remove_file(uid)
                if result and uid in self.parents:
                    subtasks = self.parents[uid]
                    for task in subtasks:
                        _remove_file(task, ignore=True)
                    print(msg)
                elif result:
                    print(msg)
            else:
                print("Cancelled")

    def edit(self, alias):
        """Edit a task identified by alias (using $EDITOR).

        Args:
            alias (str):    The alias of the task to be edited.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                filename = self.task_files.get(uid)
                if filename:
                    try:
                        subprocess.run([self.editor, filename], check=True)
                    except subprocess.SubprocessError:
                        self._handle_error(
                            f"failure editing file {filename}")
                else:
                    self._handle_error(f"failed to find file for {uid}")
        else:
            self._handle_error("$EDITOR is required and not set")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def export(self, term, filename=None):
        """Perform a search for tasks that match a given criteria and
        output the results in iCalendar VTODO format.

        Args:
            term (str):     the criteria for which to search.
            filename (str): Optional. Filename to write iCalendar VTODO
        output. This param is only useful in shell mode where
        redirection is not possible.

        """
        def _export_timestamp(timeobj):
            """Print a datetime string in iCalendar-compatible format.

            Args:
                timeobj (obj):  a datetime object.

            Returns:
                timestr (str):  a datetime string.

            """
            timestr = (timeobj.astimezone(tz=timezone.utc)
                       .strftime("%Y%m%dT%H%M%SZ"))
            return timestr

        def _export_wrap(text, length=75):
            """Wraps text that exceeds a given line length, with an
            indentation of one space on the next line.
            Args:
                text (str): the text to be wrapped.
                length (int): the maximum line length (default: 75).
            Returns:
                wrapped (str): the wrapped text.
            """
            wrapper = TextWrapper(
                width=length,
                subsequent_indent=' ',
                drop_whitespace=False,
                break_long_words=True)
            wrapped = '\r\n'.join(wrapper.wrap(text))
            return wrapped

        this_tasks = self._perform_search(term)

        if len(this_tasks) > 0:
            ical = (
                "BEGIN:VCALENDAR\r\n"
                "VERSION:2.0\r\n"
                f"PRODID:-//sdoconnell.net/{APP_NAME} {APP_VERS}//EN\r\n"
            )
            for uid in this_tasks:
                task = self._parse_task(uid)
                if task['created']:
                    created = _export_timestamp(task['created'])
                else:
                    created = _export_timestamp(
                            datetime.now(tz=self.ltz))
                if task['updated']:
                    updated = _export_timestamp(task['updated'])
                else:
                    updated = _export_timestamp(
                            datetime.now(tz=self.ltz))
                description = task['description']
                tags = task['tags']
                if tags:
                    tags = ','.join(tags).upper()
                status = task['status']
                notes = task['notes']
                parent = task['parent']
                if parent:
                    parent = self._uid_from_alias(parent)
                priority = task['priority']
                percent = task['percent']
                start = task['start']
                due = task['due']
                completed = task['completed']
                reminders = task['reminders']
                rrule = task['rrule']

                vtodo = (
                    "BEGIN:VTODO\r\n"
                    f"UID:{uid}\r\n"
                    f"DTSTAMP:{updated}\r\n"
                    f"CREATED:{created}\r\n"
                )
                if description:
                    summarytxt = _export_wrap(f"SUMMARY:{description}")
                    vtodo += f"{summarytxt}\r\n"
                if status:
                    # ical has limited range of valid status values
                    if status == "todo":
                        status = "NEEDS-ACTION"
                    elif status == "done":
                        status = "COMPLETED"
                    elif status == "cancelled":
                        status = "CANCELLED"
                    else:
                        status = "IN-PROCESS"
                    vtodo += f"STATUS:{status}\r\n"
                else:
                    # default if None
                    status = "NEEDS-ACTION"
                if due:
                    due = _export_timestamp(due)
                    vtodo += f"DUE:{due}\r\n"
                if start:
                    start = _export_timestamp(start)
                    vtodo += f"DTSTART:{start}\r\n"
                if completed:
                    completed = _export_timestamp(completed)
                    vtodo += f"COMPLETED:{completed}\r\n"
                if percent:
                    vtodo += f"PERCENT-COMPLETE:{percent}\r\n"
                if priority:
                    vtodo += f"PRIORITY:{priority}\r\n"
                if tags:
                    categoriestxt = _export_wrap(f"CATEGORIES:{tags}")
                    vtodo += f"{categoriestxt}\r\n"
                if rrule:
                    rdate = None
                    exdate = None
                    rrulekv = []
                    for key, value in rrule.items():
                        if key.lower() == "until" and value:
                            value = _export_timestamp(value)
                            rrulekv.append(f"{key}={value}")
                        elif key.lower() == "date" and value:
                            rdate_dates = []
                            for this_dt in value:
                                rdate_dates.append(
                                        _export_timestamp(this_dt))
                            rdate = ','.join(rdate_dates)
                        elif key.lower() == "except" and value:
                            except_dates = []
                            for this_dt in value:
                                except_dates.append(
                                        _export_timestamp(this_dt))
                            exdate = ','.join(except_dates)
                        elif value:
                            rrulekv.append(f"{key}={value}")
                    rrulestr = ';'.join(rrulekv).upper()
                    rruletxt = _export_wrap(f"RRULE:{rrulestr}")
                    vtodo += f"{rruletxt}\r\n"
                    if rdate:
                        rdatetxt = _export_wrap(f"RDATE:{rdate}")
                        vtodo += f"{rdatetxt}\r\n"
                    if exdate:
                        exdatetxt = _export_wrap(f"EXDATE:{exdate}")
                        vtodo += f"{exdatetxt}\r\n"
                if parent:
                    vtodo += f"RELATED-TO:{parent}\r\n"
                if notes:
                    notes = notes.replace('\n', '\\n')
                    descriptiontxt = _export_wrap(f"DESCRIPTION:{notes}")
                    vtodo += f"{descriptiontxt}\r\n"
                if reminders:
                    for reminder in reminders:
                        remind = reminder.get('remind')
                        notify = reminder.get('notify')
                        if remind:
                            remind = remind.upper()
                            vtodo += "BEGIN:VALARM\r\n"
                            dt_trigger = self._datetime_or_none(remind)
                            if dt_trigger:
                                trigger = _export_timestamp(dt_trigger)
                                vtodo += (
                                    f"TRIGGER;VALUE=DATE-TIME:{trigger}\r\n")
                            elif remind.startswith("START-"):
                                trigger = remind.replace('START-', '-PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER:{trigger}")
                                vtodo += f"{triggertxt}\r\n"
                            elif remind.startswith("START+"):
                                trigger = remind.replace('START+', 'PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER:{trigger}")
                                vtodo += f"{triggertxt}\r\n"
                            elif remind.startswith("END-"):
                                trigger = remind.replace('END-', '-PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER;RELATED=END:{trigger}")
                                vtodo += f"{triggertxt}\r\n"
                            elif remind.startswith("END+"):
                                trigger = remind.replace('END-', 'PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER;RELATED=END:{trigger}")
                                vtodo += f"{triggertxt}\r\n"
                            if notify:
                                notify = notify.upper()
                                if notify not in ["DISPLAY", "EMAIL"]:
                                    notify = "DISPLAY"
                            else:
                                notify = "DISPLAY"
                            vtodo += f"ACTION:{notify}\r\n"
                            if notify == "EMAIL" and self.user_email:
                                emailtxt = _export_wrap(
                                        f"ATTENDEE:mailto:{self.user_email}")
                                vtodo += f"{emailtxt}\r\n"
                            vtodo += "END:VALARM\r\n"

                vtodo += "END:VTODO\r\n"
                ical += vtodo
            ical += "END:VCALENDAR\r\n"

            output = ical
        else:
            output = "No records found."
        if filename:
            filename = os.path.expandvars(os.path.expanduser(filename))
            try:
                with open(filename, "w",
                          encoding="utf-8") as ical_file:
                    ical_file.write(output)
            except (OSError, IOError):
                print("ERROR: unable to write iCalendar file.")
            else:
                print(f"iCalendar data written to {filename}.")
        else:
            print(output)

    def info(self, alias, pager=False):
        """Display info about a specific task.

        Args:
            alias (str):    the task for which to provide info.
            pager (bool):   whether to page output.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            task = self._parse_task(uid)

            console = Console()

            # description, status, priority, tags, parent
            summary_table = Table(
                title=f"Task info - {task['alias']}",
                title_style=self.style_title,
                title_justify="left",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            summary_table.add_column("field", style=self.style_label)
            summary_table.add_column("data")

            # description
            descriptiontxt = Text(task['description'])
            descriptiontxt.stylize(self.style_description)
            summary_table.add_row("description:", descriptiontxt)

            # location
            if task['location']:
                locationtxt = Text(task['location'])
                locationtxt.stylize(self.style_location)
                summary_table.add_row("location:", locationtxt)

            # project
            if task['project']:
                projecttxt = Text(task['project'])
                projecttxt.stylize(
                        self._make_project_style(task['project']))
                summary_table.add_row("project:", projecttxt)

            # rrule
            if task['rrule']:
                rrule = task['rrule']
                rrulekv = []
                for key, value in rrule.items():
                    if key.lower() in ['date', 'except']:
                        pretty_dates = []
                        for item in value:
                            new_date = self._format_timestamp(
                                    item, pretty=True)
                            pretty_dates.append(new_date)
                        rrulekv.append(f"{key}={','.join(pretty_dates)}")
                    elif key.lower() == 'until':
                        value = self._format_timestamp(value, pretty=True)
                        rrulekv.append(f"{key}={value}")
                    elif value:
                        rrulekv.append(f"{key}={value}")
                rruletxt = Text(';'.join(rrulekv))
                summary_table.add_row("rrule:", rruletxt)

            # status
            if task['status']:
                statustxt = self._stylize_by_status(task['status'].upper(),
                                                    task['status'])
                summary_table.add_row("status:", statustxt)

            # priority
            if task['priority']:
                prioritytxt = self._stylize_by_priority(
                    str(task['priority']), task['priority'])
                summary_table.add_row("priority:", prioritytxt)

            # tags
            if task['tags']:
                tagtxt = Text(','.join(task['tags']))
                tagtxt.stylize(self.style_tags)
                summary_table.add_row("tags:", tagtxt)

            # parent
            if task['parent']:
                parenttxt = Text(task['parent'])
                parenttxt.stylize(self.style_parent)
                summary_table.add_row("parent:", parenttxt)

            # start, due, started, completed, percent
            if (task['start'] or
                    task['due'] or
                    task['started'] or
                    task['completed'] or
                    task['percent']):
                schedule_table = Table(
                    title="Tracking",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                schedule_table.add_column("field",
                                          style=self.style_label)
                schedule_table.add_column("data")
                now = datetime.now(tz=self.ltz)
                soon = now + timedelta(days=self.days_soon)

                # start
                if task['start']:
                    starttxt = Text(
                            self._format_timestamp(task['start'], True))
                    starttxt.stylize(self.style_date)
                    if task['status']:
                        if task['status'] == "todo":
                            if task['start'] <= now:
                                starttxt.stylize(self.style_date_late)
                            elif task['start'] <= soon:
                                starttxt.stylize(self.style_date_soon)
                    schedule_table.add_row("start date:", starttxt)

                # due
                if task['due']:
                    duetxt = Text(
                            self._format_timestamp(task['due'], True))
                    duetxt.stylize(self.style_date)
                    if task['due'] <= now:
                        duetxt.stylize(self.style_date_late)
                    elif task['due'] <= soon:
                        duetxt.stylize(self.style_date_soon)
                    else:
                        duetxt.stylize(self.style_date)
                    if task['status']:
                        if task['status'] == "done":
                            duetxt.stylize(self.style_date_done)
                    schedule_table.add_row("due date:", duetxt)

                # started
                if task['started']:
                    startedtxt = Text(self._format_timestamp(
                                        task['started'], True))
                    startedtxt.stylize(self.style_date)
                    schedule_table.add_row("started:", startedtxt)

                # completed
                if task['completed']:
                    completedtxt = Text(self._format_timestamp(
                                            task['completed'], True))
                    completedtxt.stylize(self.style_date)
                    schedule_table.add_row("completed:", completedtxt)

                # percent
                if task['percent']:
                    percenttxt = Text(f"{task['percent']}%")
                    if task['percent'] == 100:
                        percenttxt.stylize(self.style_percent_100)
                    else:
                        percenttxt.stylize(self.style_percent)
                    schedule_table.add_row("% complete:", percenttxt)

            # subtasks
            if task['uid'] in self.parents.keys():
                subtasks = self.parents[task['uid']]
                if subtasks:
                    subtasks_table = Table(
                        title="Subtasks",
                        title_style=self.style_title,
                        title_justify="left",
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        pad_edge=False,
                        collapse_padding=False,
                        padding=(0, 0, 0, 0))
                    subtasks_table.add_column("data")
                    subtasks = self._sort_tasks(subtasks, 'priority')
                    for subtask in subtasks:
                        fsubtask = self._format_task(subtask, True)
                        subtasks_table.add_row(fsubtask)

            # reminders
            if task['reminders']:
                reminder_table = Table(
                    title="Reminders",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                reminder_table.add_column("entry")

                for index, reminder in enumerate(task['reminders']):
                    remind = self._calc_reminder(
                            reminder.get('remind'),
                            task['start'],
                            task['due'])
                    if remind:
                        notify = reminder.get('notify')
                        if not notify:
                            notify = " (display)"
                        else:
                            notify = f" ({notify})"
                        remindstr = remind.strftime("%Y-%m-%d %H:%M")
                        notifytxt = Text(f"[{index + 1}] {remindstr}{notify}")
                        reminder_table.add_row(notifytxt)

            # note
            if task['notes']:
                notes_table = Table(
                    title="Notes",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                notes_table.add_column("data")
                notestxt = Text(task['notes'])
                notes_table.add_row(notestxt)

            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(summary_table)
            if 'schedule_table' in locals():
                layout.add_row(schedule_table)
            if 'subtasks_table' in locals():
                layout.add_row(subtasks_table)
            if 'reminder_table' in locals():
                layout.add_row(reminder_table)
            if 'notes_table' in locals():
                layout.add_row(notes_table)

            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)

    def list(self, view, pager=False, subs=True, project=None):
        """List tasks.

        Args:
            view (str):     the view to use (open, all, done or nosubs).
            pager (bool):   paginate output.
            subs (bool):    show subtasks.
            project (str):  show only tasks in a project.

        """
        view = view.lower()
        if project:
            project = project.lower()
        if view == "open":
            this_tasks = self._build_tree(
                self.tasks,
                'priority',
                filtexp='open',
                project=project)
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "all":
            this_tasks = self._build_tree(
                self.tasks,
                'priority',
                project=project)
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "done":
            this_tasks = self._build_flat(
                self.tasks,
                'priority',
                filtexp='done',
                project=project)
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "nosubs":
            this_tasks = self._build_tree(
                self.tasks,
                'priority',
                filtexp='open',
                subs=False,
                project=project)
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "late":
            this_tasks = self._find_late()
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "soon":
            this_tasks = self._find_soon()
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        elif view == "today":
            this_tasks = self._find_today()
            self._print_task_list(
                this_tasks,
                view,
                pager=pager,
                project=project)
        else:
            tasklist = []
            for task in self.tasks:
                if view == self.tasks[task]['alias'].lower():
                    tasklist.append(task)
            if tasklist:
                # should only be one
                uid = ''.join(tasklist)
                if uid in self.parents.keys() and subs:
                    this_tasks = self._build_tree(
                        tasklist,
                        'priority',
                        project=project)
                else:
                    this_tasks = self._build_flat(
                        tasklist,
                        'priority',
                        project=project)
                self._print_task_list(this_tasks, view, pager)
            else:
                self._handle_error(
                    "no such alias or unknown view. "
                    "Use one of: open, all, done, nosubs, soon, late, "
                    "today or <alias>"
                )

    def modify(
            self,
            alias,
            new_description=None,
            new_location=None,
            new_priority=None,
            new_tags=None,
            new_start=None,
            new_due=None,
            new_started=None,
            new_completed=None,
            new_percent=None,
            new_status=None,
            new_parent=None,
            new_project=None,
            new_rrule=None,
            add_reminder=None,
            del_reminder=None,
            new_notes=None):
        """Modify a task using provided parameters.

        Args:
            alias (str):            task alias being updated.
            new_description (str):  task description.
            new_location (str):     task location.
            new_priority (int):     task priority (1 is highest).
            new_tags (str):         tags assigned to the task.
            new_start (str):        task start date ("%Y-%m-%d[ %H:%M]").
            new_due (str):          task due date ("%Y-%m-%d[ %H:%M]").
            new_started (str):      task started date ("%Y-%m-%d[ %H:%M]").
            new_completed (str):    task completed date ("%Y-%m-%d[ %H:%M]").
            new_percent (int):      task percent complete.
            new_status (str):       task status (todo, done, ...).
            new_parent (str):       parent task (making this a subtask).
            new_project (str):      task is associated to project.
            new_rrule (str):        task recurrence rule.
            add_reminder (list):    new task reminder(s).
            del_reminder (int):     reminder index number.
            new_notes (str):        notes assigned to the task.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)

        def _remove_items(deletions, source):
            """Removes items (identified by index) from a list.
            Args:
                deletions (list):   the indexes to be deleted.
                source (list):    the list from which to remove.
            Returns:
                source (list):    the modified list.
            """
            rem_items = []
            for entry in deletions:
                try:
                    entry = int(entry)
                except ValueError:
                    pass
                else:
                    if 1 <= entry <= len(source):
                        entry -= 1
                        rem_items.append(source[entry])
            if rem_items:
                for item in rem_items:
                    source.remove(item)
            return source

        def _new_or_current(new, current):
            """Return a datetime obj for the new date (if existant and
            valid) or the current date (if existant) or None.

            Args:
                new (str):  the new timestring.
                current (obj): the current datetime object or None.

            Returns:
                updated (obj):  datetime or None.

            """
            if new:
                new = self._datetime_or_none(new)
                if new:
                    updated = new
                elif current:
                    updated = current
                else:
                    updated = None
            elif current:
                updated = current
            else:
                updated = None
            return updated

        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.task_files.get(uid)
            aliases = self._get_aliases()
            task = self._parse_task(uid)

            if filename:
                created = task['created']
                u_updated = datetime.now(tz=self.ltz)
                # start
                if new_start:
                    u_start = _new_or_current(new_start, task['start'])
                else:
                    u_start = task['start']
                # due
                if new_due:
                    u_due = _new_or_current(new_due, task['due'])
                else:
                    u_due = task['due']
                # started
                if new_started:
                    u_started = _new_or_current(new_started, task['started'])
                else:
                    u_started = task['started']
                # completed
                if new_completed:
                    u_completed = _new_or_current(
                                      new_completed, task['completed'])
                else:
                    u_completed = task['completed']
                # parent
                # check parent for existing alias
                if new_parent:
                    if new_parent.lower() not in aliases:
                        self._error_pass(
                            f"parent '{new_parent.lower()}' not found")
                        u_parent = None
                    else:
                        u_parent = new_parent.lower()
                else:
                    u_parent = task['parent']
                # description
                u_description = new_description or task['description']
                # project
                u_project = new_project or task['project']
                # location
                u_location = new_location or task['location']
                # priority
                if new_priority:
                    u_priority = self._integer_or_default(
                        new_priority, task['priority'])
                else:
                    u_priority = task['priority']
                # tags
                if new_tags:
                    new_tags = new_tags.lower()
                    if new_tags.startswith('+'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if not task['tags']:
                            tags = []
                        else:
                            tags = task['tags'].copy()
                        for new_tag in new_tags:
                            if new_tag not in tags:
                                tags.append(new_tag)
                        if tags:
                            tags.sort()
                            u_tags = tags
                        else:
                            u_tags = None
                    elif new_tags.startswith('~'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if task['tags']:
                            tags = task['tags'].copy()
                            for new_tag in new_tags:
                                if new_tag in tags:
                                    tags.remove(new_tag)
                            if tags:
                                tags.sort()
                                u_tags = tags
                            else:
                                u_tags = None
                        else:
                            u_tags = None
                    else:
                        u_tags = new_tags.split(',')
                        u_tags.sort()
                else:
                    u_tags = task['tags']
                # percent
                if new_percent:
                    u_percent = self._integer_or_default(
                        new_percent, task['percent'])
                else:
                    u_percent = task['percent']
                # status
                if new_status:
                    u_status = new_status.lower()
                else:
                    u_status = task['status']
                # reminders
                if add_reminder or del_reminder:
                    if task['reminders']:
                        u_reminders = task['reminders'].copy()
                    else:
                        u_reminders = []
                    if del_reminder and u_reminders:
                        u_reminders = _remove_items(del_reminder,
                                                    u_reminders)
                    if add_reminder:
                        for a_rem in add_reminder:
                            rem_data = {}
                            if len(a_rem) > 0:
                                rem_data['remind'] = a_rem[0]
                                if len(a_rem) == 2:
                                    remtype = str(a_rem[1]).lower()
                                    if remtype in ['display', 'email']:
                                        rem_data['notify'] = remtype
                                    else:
                                        rem_data['notify'] = 'display'
                                u_reminders.append(rem_data)
                else:
                    u_reminders = task['reminders']

                # recurrence rule
                if new_rrule:
                    u_rrule = self._parse_rrule(new_rrule)
                else:
                    u_rrule = task['rrule']

                # notes
                if new_notes:
                    # the new note is functionally empty or is using a
                    # placeholder from notes() to clear the notes
                    if new_notes in [' ', ' \n', '\n']:
                        u_notes = None
                    else:
                        u_notes = new_notes
                else:
                    u_notes = task['notes']

                data = {
                    "task": {
                        "uid": uid,
                        "created": created,
                        "updated": u_updated,
                        "alias": alias,
                        "description": u_description,
                        "location": u_location,
                        "priority": u_priority,
                        "tags": u_tags,
                        "start": u_start,
                        "due": u_due,
                        "started": u_started,
                        "completed": u_completed,
                        "percent": u_percent,
                        "status": u_status,
                        "parent": u_parent,
                        "project": u_project,
                        "rrule": u_rrule,
                        "reminders": u_reminders,
                        "notes": u_notes
                    }
                }
                # write the updated file
                self._write_yaml_file(data, filename)

                # check for 'cancelled' or 'done' status on rrule
                # tasks and create new task
                if u_rrule and u_start and u_status in ['done', 'cancelled']:
                    new_start, new_due = self._calc_next_recurrence(
                            u_rrule, u_start, u_due)
                    # convert things back to strings the way new expects
                    if u_tags:
                        u_tags = ','.join(u_tags)
                    if new_start:
                        new_start = self._format_timestamp(new_start)
                    if new_due:
                        new_due = self._format_timestamp(new_due)
                    if u_rrule:
                        rrulekv = []
                        for key, value in u_rrule.items():
                            if key.lower() in ['date', 'except']:
                                pretty_dates = []
                                for item in value:
                                    new_date = self._format_timestamp(
                                            item, pretty=True)
                                    pretty_dates.append(new_date)
                                rrulekv.append(
                                        f"{key}={','.join(pretty_dates)}")
                            elif key.lower() == 'until':
                                value = self._format_timestamp(
                                        value, pretty=True)
                                rrulekv.append(f"{key}={value}")
                            elif value:
                                rrulekv.append(f"{key}={value}")
                        u_rrule = ';'.join(rrulekv)
                    if u_reminders:
                        new_reminders = []
                        for entry in u_reminders:
                            new_reminder = []
                            remind = entry.get('remind')
                            if remind:
                                new_reminder.append(remind)
                            notify = entry.get('notify')
                            if notify:
                                new_reminder.append(notify)
                            new_reminders.append(new_reminder)
                        u_reminders = new_reminders.copy()
                    self.new(
                        description=u_description,
                        location=u_location,
                        priority=u_priority,
                        tags=u_tags,
                        start=new_start,
                        due=new_due,
                        status='todo',
                        parent=u_parent,
                        project=u_project,
                        rrule=u_rrule,
                        reminders=u_reminders,
                        notes=u_notes)

    def new(
            self,
            description=None,
            location=None,
            priority=None,
            tags=None,
            start=None,
            due=None,
            started=None,
            completed=None,
            percent=None,
            status=None,
            parent=None,
            project=None,
            rrule=None,
            reminders=None,
            notes=None):
        """Create a new task.

        Args:
            description (str):  task description.
            location (str):     task location.
            priority (int):     task priority (1 is highest).
            tags (str):         tags assigned to the task.
            start (str):        task start date ("%Y-%m-%d[ %H:%M]").
            due (str):          task due date ("%Y-%m-%d[ %H:%M]").
            completed (str):    task completed date ("%Y-%m-%d[ %H:%M]").
            percent (int):      task percent complete.
            status (str):       task status (todo, done, ...).
            parent (str):       parent task (making this a subtask).
            project (str):      task is associated with a project.
            rrule (str):        task recurrence rule.
            reminders (list):   task reminder expressions.
            notes (str):        notes assigned to the task.

        """
        uid = str(uuid.uuid4())
        now = datetime.now(tz=self.ltz)
        created = now
        updated = now
        alias = self._gen_alias()
        aliases = self._get_aliases()
        # check parent for existing alias
        if parent:
            if parent.lower() not in aliases:
                self._error_pass(f"parent '{parent.lower()}' not found")
                parent = None
        if tags:
            tags = tags.lower()
            tags = tags.split(',')
            tags.sort()
        # set defaults for empty parameters that shouldn't be empty
        description = description or "New task"
        status = status or "todo"
        # integrity checks
        if start:
            start = self._datetime_or_none(start)
        if due:
            due = self._datetime_or_none(due)
        if started:
            started = self._datetime_or_none(started)
        if completed:
            completed = self._datetime_or_none(completed)
        if priority:
            priority = self._integer_or_default(priority)
        if percent:
            percent = self._integer_or_default(percent)

        if reminders:
            new_reminders = []
            for entry in reminders:
                rem_data = {}
                if len(entry) > 0:
                    rem_data['remind'] = entry[0]
                    if len(entry) == 2:
                        remtype = str(entry[1]).lower()
                        if remtype in ['display', 'email']:
                            rem_data['notify'] = remtype
                        else:
                            rem_data['notify'] = 'display'
                    new_reminders.append(rem_data)
        else:
            new_reminders = None

        if rrule:
            new_rrule = self._parse_rrule(rrule)
        else:
            new_rrule = None

        filename = os.path.join(self.data_dir, f'{uid}.yml')
        data = {
            "task": {
                "uid": uid,
                "created": created,
                "updated": updated,
                "alias": alias,
                "description": description,
                "location": location,
                "priority": priority,
                "tags": tags,
                "start": start,
                "due": due,
                "started": started,
                "completed": completed,
                "percent": percent,
                "status": status,
                "parent": parent,
                "project": project,
                "rrule": new_rrule,
                "reminders": new_reminders,
                "notes": notes
            }
        }
        # write the updated file
        self._write_yaml_file(data, filename)
        print(f"Added task: {alias}")

    def new_task_wizard(self):
        """Prompt the user for task parameters and then call new()."""
        description = input("Description [New task]: ") or 'New task'
        location = input("Location [none]: ") or None
        status = input("Status [todo]: ") or 'todo'
        priority = input("Priority [none]: ") or None
        tags = input("Tags [none]: ") or None
        other = input("Other options? [N/y]: ").lower()
        if other in ['y', 'yes']:
            start = input("Start date [none]: ") or None
            due = input("Due date [none]: ") or None
            started = input("Date started [none]: ") or None
            completed = input("Date completed [none]: ") or None
            percent = input("Percent completed [0]: ") or None
            parent = input("Parent (if subtask) [none]: ") or None
            project = input("Project [none]: ") or None
            rrule = input("Recurrence rule [none]: ") or None
            add_reminder = input("Add reminder? [N/y]: ").lower()
            if add_reminder in ['y', 'yes']:
                self.add_new_reminder()
            else:
                self.add_reminders = None

        else:
            start = None
            due = None
            started = None
            completed = None
            percent = None
            parent = None
            self.add_reminders = None

        self.new(
            description=description,
            location=location,
            priority=priority,
            tags=tags,
            start=start,
            due=due,
            started=started,
            completed=completed,
            percent=percent,
            status=status,
            parent=parent,
            project=project,
            rrule=rrule,
            reminders=self.add_reminders,
            notes=None)

        # reset
        self.add_reminders = None

    def notes(self, alias):
        """Add or update notes on a task.

        Args:
            alias (str):        the task alias being updated.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                task = self._parse_task(uid)
                if not task['notes']:
                    fnotes = ""
                else:
                    fnotes = task['notes']
                handle, abs_path = tempfile.mkstemp()
                with os.fdopen(handle, 'w') as temp_file:
                    temp_file.write(fnotes)

                # open the tempfile in $EDITOR and then update the task
                # with the new note
                try:
                    subprocess.run([self.editor, abs_path], check=True)
                    with open(abs_path, "r",
                              encoding="utf-8") as temp_file:
                        new_note = temp_file.read()
                except subprocess.SubprocessError:
                    msg = "failure editing note"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
                else:
                    # notes were deleted entirely but if we set this to
                    # None then the note won't be updated. Set it to " "
                    # and then use special handling in modify()
                    if task['notes'] and not new_note:
                        new_note = " "
                    self.modify(
                        alias=alias,
                        new_notes=new_note)
                    os.remove(abs_path)
        else:
            self._handle_error("$EDITOR is required and not set")

    def query(self, term, limit=None, json_output=False):
        """Perform a search for tasks that match a given criteria and
        print the results in plain, tab-delimited text or JSON.

        Args:
            term (str):     the criteria for which to search.
            limit (str):    filter output to specific fields.
            json_output (bool): output in JSON format.

        """
        result_tasks = self._perform_search(term)
        if limit:
            limit = limit.split(',')
        tasks_out = {}
        tasks_out['tasks'] = []
        text_out = ""
        if len(result_tasks) > 0:
            for uid in result_tasks:
                this_task = {}
                task = self._parse_task(uid)
                created = task["created"]
                updated = task["updated"]
                description = task["description"] or ""
                location = task["location"] or ""
                alias = task["alias"] or ""
                tags = task["tags"] or []
                status = task["status"] or ""
                parent = task["parent"] or ""
                priority = task["priority"] or ""
                percent = task["percent"] or ""
                project = task["project"] or ""
                if created:
                    created = self._format_timestamp(created)
                if updated:
                    updated = self._format_timestamp(updated)
                if task["start"]:
                    start = self._format_timestamp(
                        task["start"], True)
                    j_start = self._format_timestamp(
                        task["start"])
                else:
                    start = ""
                    j_start = None
                if task["due"]:
                    due = self._format_timestamp(
                        task["due"], True)
                    j_due = self._format_timestamp(
                        task["due"])
                else:
                    due = ""
                    j_due = None
                if task["started"]:
                    started = self._format_timestamp(
                        task["started"], True)
                    j_started = self._format_timestamp(
                        task["started"])
                else:
                    started = ""
                    j_started = None
                if task["completed"]:
                    completed = self._format_timestamp(
                        task["completed"], True)
                    j_completed = self._format_timestamp(
                        task["completed"])
                else:
                    completed = ""
                    j_completed = None

                if limit:
                    output = ""
                    if "uid" in limit:
                        output += f"{uid}\t"
                    if "alias" in limit:
                        output += f"{alias}\t"
                    if "status" in limit:
                        output += f"{status}\t"
                    if "priority" in limit:
                        output += f"{priority}\t"
                    if "description" in limit:
                        output += f"{description}\t"
                    if "location" in limit:
                        output += f"{location}\t"
                    if "project" in limit:
                        output += f"{project}\t"
                    if "percent" in limit:
                        output += f"{percent}\t"
                    if "tags" in limit:
                        output += f"{tags}\t"
                    if "parent" in limit:
                        output += f"{parent}\t"
                    if "start" in limit:
                        output += f"{start}\t"
                    if "due" in limit:
                        output += f"{due}\t"
                    if "started" in limit:
                        output += f"{started}\t"
                    if "completed" in limit:
                        output += f"{completed}\t"
                    if output.endswith('\t'):
                        output = output.rstrip(output[-1])
                    output = f"{output}\n"
                else:
                    output = (
                        f"{uid}\t"
                        f"{alias}\t"
                        f"{status}\t"
                        f"{priority}\t"
                        f"{description}\t"
                        f"{location}\t"
                        f"{project}\t"
                        f"{percent}\t"
                        f"{tags}\t"
                        f"{parent}\t"
                        f"{start}\t"
                        f"{due}\t"
                        f"{started}\t"
                        f"{completed}\n"
                    )
                this_task['uid'] = uid
                this_task['created'] = created
                this_task['updated'] = updated
                this_task['alias'] = task['alias']
                this_task['status'] = task['status']
                this_task['priority'] = task['priority']
                this_task['description'] = task['description']
                this_task['location'] = task['location']
                this_task['percent'] = task['percent']
                this_task['tags'] = task['tags']
                this_task['parent'] = task['parent']
                this_task['project'] = task['project']
                this_task['rrule'] = task['rrule']
                this_task['start'] = j_start
                this_task['due'] = j_due
                this_task['started'] = j_started
                this_task['completed'] = j_completed
                this_task['reminders'] = task['reminders']
                this_task['notes'] = task['notes']
                tasks_out['tasks'].append(this_task)
                text_out += f"{output}"
        if json_output:
            json_out = json.dumps(tasks_out, indent=4)
            print(json_out)
        else:
            if text_out != "":
                print(text_out, end="")
            else:
                print("No results.")

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()

    def reminders(self, interval=None):
        """Calculates reminders for all future tasks and prints
        reminders for the interval period JSON format.

        Args:
            interval (str):     interval for future reminders (XdYhZm).

        """
        if interval:
            seconds = self._calc_duration(interval)
        else:
            seconds = 3600
        now = datetime.now(tz=self.ltz)
        b_span = now - timedelta(seconds=60)
        e_span = now + timedelta(seconds=seconds)
        reminders_out = {}
        reminders_out['reminders'] = []
        for uid in self.tasks:
            task = self._parse_task(uid)
            alias = task['alias']
            description = task['description']
            location = task['location']
            reminders = task['reminders']
            notes = task['notes']
            status = task['status']
            priority = task['priority']
            percent = task['percent']
            start = task['start']
            due = task['due']
            started = task['started']
            completed = task['completed']
            tags = task['tags']
            if reminders:
                for reminder in reminders:
                    remind = reminder.get('remind')
                    notify = reminder.get('notify')
                    if notify:
                        if notify.lower() == "email" and self.user_email:
                            notify = "email"
                        else:
                            notify = "display"
                    else:
                        notify = "display"
                    if remind:
                        dt_reminder = self._calc_reminder(
                            remind,
                            task['start'],
                            task['due'])
                    if b_span <= dt_reminder <= e_span:
                        if status:
                            status = status.upper()
                        else:
                            status = "TODO"
                        if start:
                            startstr = (
                                "start: "
                                f"{self._format_timestamp(start, True)} "
                            )
                        else:
                            startstr = ""
                        if due:
                            duestr = (
                                "due: "
                                f"{self._format_timestamp(due, True)}"
                            )
                        else:
                            duestr = ""
                        if start or due:
                            dateline = f"\n + {startstr}{duestr}"
                        else:
                            dateline = ""
                        if started:
                            startedstr = (
                                "started: "
                                f"{self._format_timestamp(started, True)} "
                            )
                        else:
                            startedstr = ""
                        if completed:
                            completedstr = (
                                "completed: "
                                f"{self._format_timestamp(completed, True)}"
                            )
                        else:
                            completedstr = ""
                        if started or completed:
                            historyline = (
                                f"\n + {startedstr}{completedstr}"
                            )
                        else:
                            historyline = ""
                        notesflag = "*" if task['notes'] else ""
                        tagline = (
                            f"\n + tags: {','.join(tags)}" if tags else ""
                        )
                        locationline = (
                            "\n + location: {location}" if location else ""
                        )
                        percentstr = f" ({percent}%)" if percent else ""
                        prioritystr = f"[{priority}] " if priority else ""
                        notesblock = f"\n\n{notes}\n" if notes else ""
                        if notify == "email":
                            body = (
                                f"({alias}) [{status}] {prioritystr}"
                                f"{description}{notesflag}{percentstr}"
                                f"{locationline}{tagline}{dateline}"
                                f"{historyline}{notesblock}\nEOF"
                            )
                        else:
                            body = (
                                f"({alias}) [{status}] {prioritystr}"
                                f"{description}{notesflag}{percentstr}"
                                f"{locationline}{tagline}{dateline}"
                                f"{historyline}"
                            )
                        this_reminder = {}
                        dtstr = dt_reminder.strftime("%Y-%m-%d %H:%M")
                        this_reminder['datetime'] = dtstr
                        this_reminder['notification'] = notify
                        if notify == "email":
                            this_reminder['address'] = self.user_email
                        this_reminder['summary'] = description
                        this_reminder['body'] = body
                        reminders_out['reminders'].append(this_reminder)
        if reminders_out['reminders']:
            json_out = json.dumps(reminders_out, indent=4)
            print(json_out)

    def search(self, term, pager=False):
        """Perform a search for tasks that match a given criteria and
        print the results in formatted text.

        Args:
            term (str):     the criteria for which to search.

        """
        this_tasks = self._perform_search(term)
        self._print_task_list(this_tasks, 'search results', pager)

    def start(self, alias):
        """Mark as task as started, update status and started date.

        Args:
            alias (str):    the alias of the task to start.

        """
        now = (datetime.now(tz=self.ltz)
               .strftime("%Y-%m-%d %H:%M:%S"))
        self.modify(
            alias=alias,
            new_started=now,
            new_percent=0,
            new_status='inprogress')

    def unset(self, alias, field):
        """Clear a specified field for a given alias.
        Args:
            alias (str):    the task alias.
            field (str):    the field to clear.
        """
        alias = alias.lower()
        field = field.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            allowed_fields = [
                'tags',
                'start',
                'due',
                'started',
                'completed',
                'priority',
                'percent',
                'parent',
                'project',
                'rrule',
                'reminders',
                'location'
            ]
            if field in allowed_fields:
                if self.tasks[uid][field]:
                    self.tasks[uid][field] = None
                    task = self._parse_task(uid)
                    filename = self.task_files.get(uid)
                    if task and filename:
                        data = {
                            "task": {
                                "uid": task['uid'],
                                "created": task['created'],
                                "updated": task['updated'],
                                "alias": task['alias'],
                                "description": task['description'],
                                "location": task['location'],
                                "priority": task['priority'],
                                "tags": task['tags'],
                                "start": task['start'],
                                "due": task['due'],
                                "started": task['started'],
                                "completed": task['completed'],
                                "percent": task['percent'],
                                "status": task['status'],
                                "parent": task['parent'],
                                "project": task['project'],
                                "rrule": task['rrule'],
                                "reminders": task['reminders'],
                                "notes": task['notes']
                            }
                        }
                        # write the updated file
                        self._write_yaml_file(data, filename)
            else:
                self._handle_error(f"cannot clear field '{field}'")


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.

    Attributes:
        shell (obj):    the calling shell object.

    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.

        Args:
            event (obj):    file system event.

        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class TasksShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        tasks (obj):     an instance of Tasks().

    """
    def __init__(
            self,
            tasks,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a TasksShell() object."""
        super().__init__()
        self.tasks = tasks

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.tasks.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args.startswith("lsa"):
            newargs = args.split()
            newargs[0] = "all"
            self.do_list(' '.join(newargs))
        elif args.startswith("lso"):
            newargs = args.split()
            newargs[0] = "open"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsd"):
            newargs = args.split()
            newargs[0] = "done"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsn"):
            newargs = args.split()
            newargs[0] = "nosubs"
            self.do_list(' '.join(newargs))
        elif args.startswith("lss"):
            newargs = args.split()
            newargs[0] = "soon"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsl"):
            newargs = args.split()
            newargs[0] = "late"
            self.do_list(' '.join(newargs))
        elif args.startswith("lst"):
            newargs = args.split()
            newargs[0] = "today"
            self.do_list(' '.join(newargs))
        elif args.startswith("ls"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_list(' '.join(newargs[1:]))
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_delete(' '.join(newargs[1:]))
            else:
                self.do_delete("")
        elif args.startswith("mod"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_modify(' '.join(newargs[1:]))
            else:
                self.do_modify("")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.tasks.color_bold:
            self.prompt = "\033[1mtasks\033[0m> "
        else:
            self.prompt = "tasks> "

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the task for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for task in self.tasks.tasks:
            this_alias = self.tasks.tasks[task].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = task
        return uid

    def do_archive(self, args):
        """Archive a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.archive(str(commands[0]).lower())
        else:
            self.help_archive()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_complete(self, args):
        """Complete a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.complete(str(commands[0]).lower())
        else:
            self.help_complete()

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.tasks.edit_config()

    def do_delete(self, args):
        """Delete a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.delete(str(commands[0]).lower())
        else:
            self.help_delete()

    def do_edit(self, args):
        """Edit a task via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.edit(str(commands[0]).lower())
        else:
            self.help_edit()

    def do_export(self, args):
        """Search for task(s) and export to an iCalendar file.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) == 2:
                term = str(commands[0]).lower()
                filename = str(commands[1])
                self.tasks.export(term, filename)
            else:
                self.help_export()
        else:
            self.help_export()

    @staticmethod
    def do_exit(args):
        """Exit the tasks shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_info(self, args):
        """Output info about a task.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            page = False
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    page = True
            self.tasks.info(alias, page)
        else:
            self.help_info()

    def do_list(self, args):
        """Output a list of tasks.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            args = args.strip()
            pager = False
            if args.endswith('|'):
                pager = True
                args = args[:-1].strip()
            commands = args.split()
            view = str(commands[0]).lower()
            if len(commands) > 1:
                project = commands[1]
            else:
                project = None
            self.tasks.list(view, pager=pager, project=project)
        else:
            self.help_list()

    def do_modify(self, args):
        """Modify a task.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                print(f"Alias '{alias}' not found")
            else:
                subshell = ModShell(self.tasks, uid, alias)
                subshell.cmdloop()
        else:
            self.help_modify()

    def do_new(self, args):
        """Evoke the new task wizard.

        Args:
            args (str): the command arguments, ignored.

        """
        try:
            self.tasks.new_task_wizard()
        except KeyboardInterrupt:
            print("\nCancelled.")

    def do_notes(self, args):
        """Edit task notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.notes(str(commands[0]).lower())
        else:
            self.help_notes()

    def do_refresh(self, args):
        """Refresh task information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.tasks.refresh()
        if args != 'silent':
            print("Data refreshed.")

    def do_search(self, args):
        """Search for tasks that meet certain criteria.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.tasks.search(term, page)
        else:
            self.help_search()

    def do_start(self, args):
        """Start a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.tasks.start(str(commands[0]).lower())
        else:
            self.help_start()

    def help_archive(self):
        """Output help for 'archive' command."""
        print(
            '\narchive <alias>:\n'
            f'    Archive a task file to {self.tasks.data_dir}/archive.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_complete():
        """Output help for 'complete' command."""
        print(
            '\ncomplete <alias>:\n'
            '    Complete a task (set status to \'done\', percent to '
            '100, and update the \'completed\' date).\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete a task file.\n'
        )

    @staticmethod
    def help_edit():
        """Output help for 'edit' command."""
        print(
            '\nedit <alias>:\n'
            '    Edit a task file with $EDITOR.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the tasks shell.\n'
        )

    @staticmethod
    def help_export():
        """Output help for 'export' command."""
        print(
            '\nexport <term> <file>:\n'
            '    Perform a search and export the results to a file '
            'in iCalendar format.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo <alias>:\n'
            '    Show info about a task.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) <view> [|]:\n'
            '    List tasks using one of the views \'open\', \'all\', '
            '\'done\', \'nosubs\', \'soon\', \'late\', \'today\' or '
            '<alias>. Optionally, you may add a project name as a second '
            'argument to show only tasks from that project. '
            'Add \'|\' as an additional argument to page the output.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      lsa : list all\n'
            '      lso : list open\n'
            '      lsd : list done\n'
            '      lsn : list nosubs\n'
            '      lss : list soon\n'
            '      lsl : list late\n'
            '      lst : list today\n'
        )

    @staticmethod
    def help_modify():
        """Output help for 'modify' command."""
        print(
            '\nmodify <alias>:\n'
            '    Modify a task file.\n'
        )

    @staticmethod
    def help_new():
        """Output help for 'new' command."""
        print(
            '\nnew:\n'
            '    Create new task interactively.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes <alias>:\n'
            '    Edit the notes on a task with $EDITOR. This is safer '
            'than editing the task directly with \'edit\', as it will '
            'ensure proper indentation for multi-line notes.\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the task information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term>:\n'
            '    Search for a task or tasks that meet some specified '
            'criteria.\n'
        )

    @staticmethod
    def help_start():
        """Output help for 'start' command."""
        print(
            '\nstart <alias>:\n'
            '    Start a task (set status to \'inprogress\', percent to'
            ' 0, and update the \'started\' date).\n'
        )


class ModShell(Cmd):
    """Subshell for modifying a task.

    Attributes:
        tasks (obj):    an instance of Tasks().
        uid (str):      the uid of the task being modified.
        alias (str):    the alias of the task being modified.

    """
    def __init__(
            self,
            tasks,
            uid,
            alias,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ModShell() object."""
        super().__init__()
        self.tasks = tasks
        self.uid = uid
        self.alias = alias

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "ls":
            self.do_list("")
        elif args.startswith("del") or args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                newargs.pop(0)
                newargs = ' '.join(newargs)
                self.do_delete(newargs)
            else:
                self.do_delete("")
        elif args.startswith("quit") or args.startswith("exit"):
            return True
        else:
            print("\nNo such command. See 'help'.\n")

    @staticmethod
    def emptyline():
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.tasks.color_bold:
            self.prompt = f"\033[1mmodify ({self.alias})\033[0m> "
        else:
            self.prompt = f"modify ({self.alias})> "

    def do_add(self, args):
        """Add a reminder to a task.
        Args:
            args (str): the command arguments.
        """
        commands = args.split()
        if len(commands) < 1:
            self.help_add()
        else:
            attr = str(commands[0]).lower()
            if attr == 'reminder':
                try:
                    self.tasks.add_new_reminder(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.tasks.modify(
                    alias=self.alias,
                    add_reminder=self.tasks.add_reminders)
                self.tasks.add_reminders = None
            else:
                self.help_add()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_completed(self, args):
        """Modify the 'completed' date on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            completed = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_completed=completed)
        else:
            self.help_completed()

    def do_delete(self, args):
        """Delete a reminder from a task.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) < 2:
            self.help_delete()
        else:
            attr = str(commands[0]).lower()
            index = commands[1]
            if attr == 'reminder':
                reminder = [index]
                self.tasks.modify(
                    alias=self.alias,
                    del_reminder=reminder)
            else:
                self.help_delete()

    def do_description(self, args):
        """Modify the description on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            description = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_description=description)
        else:
            self.help_description()

    @staticmethod
    def do_done(args):
        """Exit the modify subshell.

        Args:
            args (str): the command arguments, ignored.

        """
        return True

    def do_due(self, args):
        """Modify the 'due' date on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            due = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_due=due)
        else:
            self.help_due()

    def do_info(self, args):
        """Display full details for the selected task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if str(commands[0]) == "|":
                self.tasks.info(self.alias, True)
            else:
                self.tasks.info(self.alias)
        else:
            self.tasks.info(self.alias)

    def do_list(self, args):
        """Output the task.

        Args:
            args (str): the command arguments.

        """
        self.tasks.list(self.alias, False, False)

    def do_location(self, args):
        """Modify the location on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            location = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_location=location)
        else:
            self.help_location()

    def do_notes(self, args):
        """Edit task notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        self.tasks.notes(self.alias)

    def do_parent(self, args):
        """Modify the parent of a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            parent = str(commands[0]).lower()
            self.tasks.modify(
                alias=self.alias,
                new_parent=parent)
        else:
            self.help_parent()

    def do_percent(self, args):
        """Modify the percent complete of a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            percent = commands[0]
            self.tasks.modify(
                alias=self.alias,
                new_percent=percent)
        else:
            self.help_percent()

    def do_priority(self, args):
        """Modify the priority of a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            priority = commands[0]
            self.tasks.modify(
                alias=self.alias,
                new_priority=priority)
        else:
            self.help_priority()

    def do_project(self, args):
        """Modify the project on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            project = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_project=project)
        else:
            self.help_project()

    def do_rrule(self, args):
        """Modify the rrule on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            rrule = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_rrule=rrule)
        else:
            self.help_rrule()

    def do_start(self, args):
        """Modify the 'start' date on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            start = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_start=start)
        else:
            self.help_start()

    def do_started(self, args):
        """Modify the 'started' date on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            started = str(args)
            self.tasks.modify(
                alias=self.alias,
                new_started=started)
        else:
            self.help_started()

    def do_status(self, args):
        """Modify the status of a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            status = str(commands[0]).lower()
            self.tasks.modify(
                alias=self.alias,
                new_status=status)
        else:
            self.help_status()

    def do_tags(self, args):
        """Modify the tags on a task.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            tags = str(commands[0])
            self.tasks.modify(
                alias=self.alias,
                new_tags=tags)
        else:
            self.help_tags()

    def do_unset(self, args):
        """Clear a field on the task.
        Args:
            args (str):     the command arguments.
        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) > 2:
                self.help_unset()
            else:
                field = str(commands[0]).lower()
                allowed_fields = [
                        'tags',
                        'start',
                        'due',
                        'started',
                        'completed',
                        'priority',
                        'percent',
                        'parent',
                        'project',
                        'rrule',
                        'reminders',
                        'location'
                ]
                if field in allowed_fields:
                    self.tasks.unset(self.alias, field)
                else:
                    self.help_unset()
        else:
            self.help_unset()

    @staticmethod
    def help_add():
        """Output help for 'add' command."""
        print(
            '\nadd reminder:\n'
            '    Add a reminder to a task record. The expression can '
            'either be a relative duration (e.g., start-15m or '
            'due+1h) or may be a date/time expression in the form '
            '%Y-%m-%d [%H:%M]. The notification can be either "email" '
            '(for a reminder email) or "display" for an on-screen '
            'notification.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_completed():
        """Output help for 'completed' command."""
        print(
            '\ncompleted: <%Y-%m-%d[ %H:%M]>\n'
            '    Modify the \'completed\' date on the task.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (del, rm) reminder <number>:\n'
            '    Delete a reminder from a task record, identified by '
            'the index number for the reminder.\n'
        )

    @staticmethod
    def help_description():
        """Output help for 'description' command."""
        print(
            '\ndescription <description>:\n'
            '    Modify the description of the task.\n'
        )

    @staticmethod
    def help_done():
        """Output help for 'done' command."""
        print(
            '\ndone:\n'
            '    Finish modifying the task.\n'
        )

    @staticmethod
    def help_due():
        """Output help for 'due' command."""
        print(
            '\ndue <%Y-%m-%d[ %H:%M]>:\n'
            '    Modify the \'due\' date on the task.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for a task. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'print' command."""
        print(
            '\nlist:\n'
            '    Show the current task entry.\n'
        )

    @staticmethod
    def help_location():
        """Output help for 'location' command."""
        print(
            '\nlocation <location>:\n'
            '    Modify the location of the task.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes:\n'
            '    Edit the notes on this task with $EDITOR.\n'
        )

    @staticmethod
    def help_parent():
        """Output help for 'parent' command."""
        print(
            '\nparent <alias>:\n'
            '    Modify the parent task of this task.\n'
        )

    @staticmethod
    def help_percent():
        """Output help for 'percent' command."""
        print(
            '\npercent <int>:\n'
            '    Modify the percent complete of the task.\n'
        )

    @staticmethod
    def help_priority():
        """Output help for 'priority' command."""
        print(
            '\npriority <int>:\n'
            '    Modify the priority of the task.\n'
        )

    @staticmethod
    def help_project():
        """Output help for 'project' command."""
        print(
            '\nproject <project>:\n'
            '    Modify the project of this task.\n'
        )

    @staticmethod
    def help_rrule():
        """Output help for 'rrule' command."""
        print(
            '\nrrule:\n'
            '    Modify the recurrence rule of this task. The rrule '
            'expression is a comma-delimited list of key/value pairs. '
            'The following keys are supported:\n'
            '  date=          - specific recurrence date(s), delimited '
            'by semicolon (;)\n'
            '  except=        - specific exception date(s), delimited '
            'by semicolon (;)\n'
            '  freq=          - one of minutely, hourly, daily, weekly, '
            'monthly, or yearly\n'
            '  count=         - number of recurrences\n'
            '  until=         - specific end date for recurrence\n'
            '  interval=      - integer value for recurrence interval\n'
            '  byhour=        - recur by hour (0-23)\n'
            '  byweekday=     - one of SU, MO, TU, WE, TH, FR, SA\n'
            '  bymonth=       - recur by month (1-12)\n'
            '  bymonthday=    - day of month (1-31)\n'
            '  byyearday=     - day of the year (1-366)\n'
            '  byweekno=      - week of year (1-53)\n'
            '  bysetpos=      - position of occurence set (e.g., 1 for '
            'first, -1 for last, -2 for second to last\n'
        )

    @staticmethod
    def help_start():
        """Output help for 'start' command."""
        print(
            '\nstart <%Y-%m-%d[ %H:%M]>:\n'
            '    Modify the \'start\' date on the task.\n'
        )

    @staticmethod
    def help_started():
        """Output help for 'started' command."""
        print(
            '\nstarted <%Y-%m-%d[ %H:%M]>:\n'
            '    Modify the \'started\' date on the task.\n'
        )

    @staticmethod
    def help_status():
        """Output help for 'status' command."""
        print(
            '\nstatus <status>:\n'
            '    Modify the status of the task.\n'
        )

    @staticmethod
    def help_tags():
        """Output help for 'tags' command."""
        print(
            '\ntags <tag>[,tag]:\n'
            '    Modify the tags on the task. A comma-delimted list or '
            'you may use the + and ~ notations to add or delete a tag '
            'from the existing tags.\n'
        )

    @staticmethod
    def help_unset():
        """Output help for 'unset' command."""
        print(
            '\nunset <alias> <field>:\n'
            '    Clear a specified field of the task. The field may '
            'be one of the following: tags, start, due, started, '
            'completed, priority, percent, parent, project, or rrule.\n'
        )


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based task management for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    archive = subparsers.add_parser(
        'archive',
        help='archive a task')
    archive.add_argument(
        'alias',
        help='task alias')
    archive.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="archive without confirmation")
    archive.set_defaults(command='archive')
    complete = subparsers.add_parser(
        'complete',
        help='complete a task')
    complete.add_argument(
        'alias',
        help='task alias')
    complete.set_defaults(command='complete')
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete a task file')
    delete.add_argument(
        'alias',
        help='task alias')
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    edit = subparsers.add_parser(
        'edit',
        help='edit a task file (uses $EDITOR)')
    edit.add_argument(
        'alias',
        help='task alias')
    edit.set_defaults(command='edit')
    export = subparsers.add_parser(
        'export',
        help='export tasks to iCalendar-formatted VTODO output')
    export.add_argument(
        'term',
        help='search term')
    export.set_defaults(command='export')
    info = subparsers.add_parser(
        'info',
        parents=[pager],
        help='show info about a task')
    info.add_argument(
        'alias',
        help='the task to view')
    info.set_defaults(command='info')
    listcmd = subparsers.add_parser(
        'list',
        aliases=['ls'],
        parents=[pager],
        help='list tasks')
    listcmd.add_argument(
        'view',
        help='list view (open, done, etc.) or <alias>')
    listcmd.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    listcmd.set_defaults(command='list')
    # list shortcuts
    lso = subparsers.add_parser('lso', parents=[pager])
    lso.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lso.set_defaults(command='lso')
    lss = subparsers.add_parser('lss', parents=[pager])
    lss.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lss.set_defaults(command='lss')
    lsl = subparsers.add_parser('lsl', parents=[pager])
    lsl.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lsl.set_defaults(command='lsl')
    lst = subparsers.add_parser('lst', parents=[pager])
    lst.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lst.set_defaults(command='lst')
    lsd = subparsers.add_parser('lsd', parents=[pager])
    lsd.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lsd.set_defaults(command='lsd')
    lsn = subparsers.add_parser('lsn', parents=[pager])
    lsn.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lsn.set_defaults(command='lsn')
    lsa = subparsers.add_parser('lsa', parents=[pager])
    lsa.add_argument(
        '--project',
        metavar='<project>',
        help='show only tasks in project')
    lsa.set_defaults(command='lsa')
    modify = subparsers.add_parser(
        'modify',
        aliases=['mod'],
        help='modify a task')
    modify.add_argument(
        'alias',
        help='the task to modify')
    modify.add_argument(
        '--completed',
        metavar='<datetime>',
        help='completed datetime: YYYY-mm-dd[ HH:MM]')
    modify.add_argument(
        '--description',
        metavar='<description>',
        help='task description')
    modify.add_argument(
        '--due',
        metavar='<datetime>',
        help='due datetime: YYYY-mm-dd[ HH:MM]')
    modify.add_argument(
        '--location',
        metavar='<location>',
        help='task location')
    modify.add_argument(
        '--notes',
        metavar='<text>',
        help='notes about the task')
    modify.add_argument(
        '--parent',
        metavar='<alias>',
        help='task is subtask of <alias>')
    modify.add_argument(
        '--percent',
        metavar='<number>',
        help='percent complete')
    modify.add_argument(
        '--priority',
        metavar='<number>',
        help='task priority')
    modify.add_argument(
        '--project',
        metavar='<project>',
        help='task project')
    modify.add_argument(
        '--rrule',
        metavar='<rule>',
        help='task recurrence rule')
    modify.add_argument(
        '--start',
        metavar='<datetime>',
        help='start datetime: YYYY-mm-dd[ HH:MM]')
    modify.add_argument(
        '--started',
        metavar='<datetime>',
        help='started datetime: YYYY-mm-dd[ HH:MM]')
    modify.add_argument(
        '--status',
        metavar='<status>',
        help='task status [done, todo, ...]')
    modify.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='task tag(s)')
    modify.add_argument(
        '--add-reminder',
        metavar=('<datetime|expression>', 'display|email'),
        nargs='+',
        dest='add_reminder',
        action='append',
        help='add task reminder')
    modify.add_argument(
        '--del-reminder',
        metavar='<index>',
        dest='del_reminder',
        action='append',
        help='delete task reminder')
    modify.set_defaults(command='modify')
    new = subparsers.add_parser(
        'new',
        help='create a new task')
    new.add_argument(
        'description',
        help='task description')
    new.add_argument(
        '--completed',
        metavar='<datetime>',
        help=r'completed datetime: YYYY-mm-dd[ HH:MM]')
    new.add_argument(
        '--due',
        metavar='<datetime>',
        help=r'due datetime: YYYY-mm-dd[ HH:MM]')
    new.add_argument(
        '--location',
        metavar='<location>',
        help='task location')
    new.add_argument(
        '--notes',
        metavar='<text>',
        help='notes about the task')
    new.add_argument(
        '--parent',
        metavar='<alias>',
        help='task is subtask of <alias>')
    new.add_argument(
        '--percent',
        metavar='<number>',
        help='task percent complete')
    new.add_argument(
        '--priority',
        metavar='<number>',
        help='task priority')
    new.add_argument(
        '--project',
        metavar='<project>',
        help='task project')
    new.add_argument(
        '--reminder',
        metavar=('<datetime|expression>', 'display|email'),
        nargs='+',
        action='append',
        dest='reminders',
        help='reminder date/time or relative expression')
    new.add_argument(
        '--rrule',
        metavar='<rule>',
        help='task recurrence rule')
    new.add_argument(
        '--start',
        metavar='<datetime>',
        help=r'start datetime: YYYY-mm-dd[ HH:MM]')
    new.add_argument(
        '--started',
        metavar='<datetime>',
        help=r'started datetime: YYYY-mm-dd[ HH:MM]')
    new.add_argument(
        '--status',
        metavar='<status>',
        help='task status [done, todo, ...]')
    new.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='task tag(s)')
    new.set_defaults(command='new')
    notes = subparsers.add_parser(
        'notes',
        help='add/update notes on a task (uses $EDITOR)')
    notes.add_argument(
        'alias',
        help='task alias')
    notes.set_defaults(command='notes')
    query = subparsers.add_parser(
        'query',
        help='search tasks with structured text output')
    query.add_argument(
        'term',
        help='search term')
    query.add_argument(
        '-l',
        '--limit',
        dest='limit',
        help='limit output to specific field(s)')
    query.add_argument(
        '-j',
        '--json',
        dest='json',
        action='store_true',
        help='output as JSON rather than TSV')
    query.set_defaults(command='query')
    reminders = subparsers.add_parser(
        'reminders',
        aliases=['rem'],
        help='task reminders')
    reminders.add_argument(
        'interval',
        help='reminder interval ([Xd][Yh][Zd])')
    reminders.set_defaults(command='reminders')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search tasks')
    search.add_argument(
        'term',
        help='search term')
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    start = subparsers.add_parser(
        'start',
        help='start a task')
    start.add_argument(
        'alias',
        help='task alias')
    start.set_defaults(command='start')
    unset = subparsers.add_parser(
        'unset',
        help='clear a field from a specified task')
    unset.add_argument(
        'alias',
        help='task alias')
    unset.add_argument(
        'field',
        help='field to clear')
    unset.set_defaults(command='unset')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Tasks() object, calls
    requested method and parameters.

    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    tasks = Tasks(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "config":
        tasks.edit_config()
    elif args.command == "modify":
        tasks.modify(
            alias=args.alias,
            new_description=args.description,
            new_location=args.location,
            new_priority=args.priority,
            new_tags=args.tags,
            new_start=args.start,
            new_due=args.due,
            new_started=args.started,
            new_completed=args.completed,
            new_percent=args.percent,
            new_status=args.status,
            new_parent=args.parent,
            new_project=args.project,
            new_rrule=args.rrule,
            add_reminder=args.add_reminder,
            del_reminder=args.del_reminder,
            new_notes=args.notes)
    elif args.command == "new":
        tasks.new(
            description=args.description,
            location=args.location,
            priority=args.priority,
            tags=args.tags,
            start=args.start,
            due=args.due,
            started=args.started,
            completed=args.completed,
            percent=args.percent,
            status=args.status,
            parent=args.parent,
            project=args.project,
            rrule=args.rrule,
            reminders=args.reminders,
            notes=args.notes)
    elif args.command == "info":
        tasks.info(args.alias, args.page)
    elif args.command == "reminders":
        tasks.reminders(args.interval)
    elif args.command == "list":
        tasks.list(args.view, pager=args.page, project=args.project)
    elif args.command == "lso":
        tasks.list('open', pager=args.page, project=args.project)
    elif args.command == "lsl":
        tasks.list('late', pager=args.page, project=args.project)
    elif args.command == "lss":
        tasks.list('soon', pager=args.page, project=args.project)
    elif args.command == "lst":
        tasks.list('today', pager=args.page, project=args.project)
    elif args.command == "lsa":
        tasks.list('all', pager=args.page, project=args.project)
    elif args.command == "lsn":
        tasks.list('nosubs', pager=args.page, project=args.project)
    elif args.command == "lsd":
        tasks.list('done', pager=args.page, project=args.project)
    elif args.command == "delete":
        tasks.delete(args.alias, args.force)
    elif args.command == "edit":
        tasks.edit(args.alias)
    elif args.command == "notes":
        tasks.notes(args.alias)
    elif args.command == "start":
        tasks.start(args.alias)
    elif args.command == "complete":
        tasks.complete(args.alias)
    elif args.command == "archive":
        tasks.archive(args.alias, args.force)
    elif args.command == "search":
        tasks.search(args.term, args.page)
    elif args.command == "query":
        tasks.query(args.term, limit=args.limit, json_output=args.json)
    elif args.command == "export":
        tasks.export(args.term)
    elif args.command == "unset":
        tasks.unset(args.alias, args.field)
    elif args.command == "shell":
        tasks.interactive = True
        shell = TasksShell(tasks)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
