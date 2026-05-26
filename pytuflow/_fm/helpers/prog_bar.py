import typing


class ProgBar:

    def __init__(self, callback: typing.Callable) -> None:
        self.callback = callback
        self.next_minor_prog = 0
        self.next_major_prog = 0
        self.prog_minor_inc = 2
        self.prog_major_inc = 10

    def reset(self) -> None:
        self.next_minor_prog = self.prog_minor_inc
        self.next_major_prog = self.prog_major_inc

    def progress_callback(self, cur_prog: int, size: int) -> None:
        if self.next_minor_prog > 100:
            return
        prog = int((cur_prog / size) * 100)
        while True:
            if prog >= self.next_minor_prog and self.next_minor_prog < self.next_major_prog:
                prog_ = self.next_minor_prog
                self.next_minor_prog += self.prog_minor_inc
            elif prog >= self.next_major_prog:
                prog_ = self.next_major_prog
                if self.next_minor_prog == self.next_major_prog:
                    self.next_minor_prog += self.prog_minor_inc
                self.next_major_prog += self.prog_major_inc

            else:
                break
            self.callback(prog_)