import sublime

from project import Project

import os
import pipes
import subprocess
import thread


class SbtRunner(object):

    runners = {}

    @classmethod
    def get_runner(cls, window):
        if window.id() not in cls.runners:
            cls.runners[window.id()] = SbtRunner(window)
        return cls.runners[window.id()]

    @classmethod
    def is_sbt_running_for(cls, window):
        return cls.get_runner(window).is_sbt_running()

    def __init__(self, window):
        self._project = Project.get_project(window)
        self._proc = None

    def project_root(self):
        return self._project.project_root()

    def sbt_command(self, command):
        cmdline = self._project.sbt_command()
        if command is not None:
            cmdline.append(command)
        return cmdline

    def start_sbt(self, command, on_start, on_stop, on_stdout, on_stderr):
        if self.project_root() and not self.is_sbt_running():
            self._proc = self._try_start_sbt_proc(self.sbt_command(command))
            if self._proc is not None:
                on_start()
                if self._proc.stdout:
                    thread.start_new_thread(self._monitor_output,
                                            (self._proc.stdout, on_stdout))
                if self._proc.stderr:
                    thread.start_new_thread(self._monitor_output,
                                            (self._proc.stderr, on_stderr))
                thread.start_new_thread(self._monitor_proc, (on_stop,))

    def stop_sbt(self):
        if self.is_sbt_running():
            self._proc.terminate()

    def kill_sbt(self):
        if self.is_sbt_running():
            self._proc.kill()

    def is_sbt_running(self):
        return (self._proc is not None) and (self._proc.returncode is None)

    def send_to_sbt(self, input):
        if self.is_sbt_running():
            self._proc.stdin.write(input)
            self._proc.stdin.flush()

    def _try_start_sbt_proc(self, cmdline):
        try:
            return self._start_sbt_proc(cmdline)
        except OSError:
            msg = ('Unable to find "%s".\n\n'
                   'You may need to specify the full path to your sbt command.'
                   % cmdline[0])
            sublime.error_message(msg)

    def _start_sbt_proc(self, cmdline):
        return self._popen(cmdline,
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           cwd=self.project_root())

    def _popen(self, cmdline, **kwargs):
        if sublime.platform() == 'windows':
            return self._popen_windows(cmdline, **kwargs)
        else:
            return self._popen_unix(cmdline, **kwargs)

    def _popen_unix(self, cmdline, **kwargs):
        cmd = ' '.join(map(pipes.quote, cmdline))
        return subprocess.Popen(['/bin/bash', '-lc', cmd], **kwargs)

    def _popen_windows(self, cmdline, **kwargs):
        return subprocess.Popen(cmdline, **kwargs)

    def _monitor_output(self, pipe, handle_output):
        while True:
            output = os.read(pipe.fileno(), 2 ** 15)
            if output != "":
                handle_output(output)
            else:
                pipe.close()
                return

    def _monitor_proc(self, handle_stop):
        self._proc.wait()
        sublime.set_timeout(handle_stop, 0)
