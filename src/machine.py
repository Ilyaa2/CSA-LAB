from __future__ import annotations

import logging
import sys
from enum import Enum
from typing import ClassVar

from isa import OpcodeType, read_code


class Selector(str, Enum):
    PREV_FROM_STACK = "prev_from_stack"
    PREV_FROM_TOP = "prev_from_top"

    TOP_FROM_PREV = "top_from_prev"
    TOP_FROM_ALU = "top_from_alu"
    TOP_FROM_STACK = "top_from_stack"
    TOP_FROM_IMMEDIATE = "top_from_immediate"
    TOP_FROM_INPUT = "top_from_input"
    TOP_FROM_RETSTACK = "top_from_retstack"
    TOP_FROM_MEM = "top_from_mem"

    SP_INC = "sp_inc"
    SP_DEC = "sp_dec"

    STACK_FROM_PREV = "stack_from_prev"
    STACK_FROM_TOP = "stack_from_top"

    RSP_INC = "rsp_inc"
    RSP_DEC = "rsp_dec"

    RETSTACK_FROM_PC = "retstack_from_pc"
    RETSTACK_FROM_TOP = "retstack_from_top"

    PC_IMMEDIATE = "pc_immediate"
    PC_INC = "pc_inc"
    PC_RET = "pc_ret"

    def __str__(self) -> str:
        return str(self.value)


class ALUOpcode(str, Enum):
    INC_A = "inc_a"
    INC_B = "inc_b"
    DEC_A = "dec_a"
    DEC_B = "dec_b"
    ADD = "add"
    MUL = "mul"
    DIV = "div"
    SUB = "sub"
    MOD = "mod"
    EQ = "eq"
    GR = "gr"
    LS = "ls"


class ALU:
    alu_operations: ClassVar = [
        ALUOpcode.ADD,
        ALUOpcode.MUL,
        ALUOpcode.DIV,
        ALUOpcode.SUB,
        ALUOpcode.MOD,
        ALUOpcode.EQ,
        ALUOpcode.GR,
        ALUOpcode.LS,
    ]

    def __init__(self):
        self.result = 0
        self.src_a = None
        self.src_b = None
        self.operation = None

    def calc(self) -> None:
        if self.operation == ALUOpcode.ADD:
            self.result = self.src_a + self.src_b
        elif self.operation == ALUOpcode.MUL:
            self.result = self.src_a * self.src_b
        elif self.operation == ALUOpcode.DIV:
            self.result = self.src_b // self.src_a
        elif self.operation == ALUOpcode.SUB:
            self.result = self.src_b - self.src_a
        elif self.operation == ALUOpcode.MOD:
            self.result = self.src_b % self.src_a
        elif self.operation in [ALUOpcode.EQ, ALUOpcode.GR, ALUOpcode.LS]:
            self.calc_op_comparison()
        else:
            raise f"Unknown ALU operation: {self.operation}"

    def calc_op_comparison(self) -> None:
        if self.operation == ALUOpcode.EQ:
            self.result = int(self.src_a == self.src_b)
        elif self.operation == ALUOpcode.GR:
            self.result = int(self.src_a < self.src_b)
        elif self.operation == ALUOpcode.LS:
            self.result = int(self.src_a >= self.src_b)

    def set_details(self, src_a, src_b, operation: ALUOpcode) -> None:
        self.src_a = src_a
        self.src_b = src_b
        self.operation = operation


class DataPath:
    def __init__(
        self,
        memory_size: int,
        return_stack_size: int,
        data_stack_size: int,
        input_buffer: list,
    ):
        assert memory_size > 0, "memory size should be greater than zero"
        assert return_stack_size > 0, "return_stack size should be greater than zero"
        assert data_stack_size > 0, "data_stack size should be greater than zero"

        self.alu = ALU()

        self.pc = 0
        self.sp = 0
        self.rsp = 0
        self.top = 4444
        self.prev = 4444

        self.memory_size = memory_size
        self.data_memory = [1111] * memory_size
        self.return_stack_size = return_stack_size
        self.return_stack = [2222] * return_stack_size
        self.data_stack_size = data_stack_size
        self.data_stack = [3333] * data_stack_size
        self.input_buffer = input_buffer
        self.output_buffer_symbols = []
        self.output_buffer_nums = []

    def signal_latch_rsp(self, selector: Selector) -> None:
        if selector is Selector.RSP_DEC:
            self.rsp -= 1
        elif selector is Selector.RSP_INC:
            self.rsp += 1

    def signal_latch_sp(self, selector: Selector) -> None:
        if selector is Selector.SP_DEC:
            self.sp -= 1
        elif selector is Selector.SP_INC:
            self.sp += 1

    def signal_stack_wr(self, selector: Selector) -> None:
        assert self.sp >= 0, "Data stack underflow"
        assert self.sp < self.data_stack_size, "Data stack overflow"
        if selector is Selector.STACK_FROM_TOP:
            self.data_stack[self.sp] = self.top
        if selector is Selector.STACK_FROM_PREV:
            self.data_stack[self.sp] = self.prev

    def signal_retstack_wr(self, selector: Selector) -> None:
        assert self.rsp >= 0, "Return stack underflow"
        assert self.rsp < self.return_stack_size, "Return stack overflow"
        if selector is Selector.RETSTACK_FROM_PC:
            self.return_stack[self.rsp] = self.pc
        elif selector is Selector.RETSTACK_FROM_TOP:
            self.return_stack[self.rsp] = self.top

    def signal_latch_pc(self, selector: Selector, immediate=0) -> None:
        if selector is Selector.PC_INC:
            self.pc += 1
        elif selector is Selector.PC_RET:
            self.pc = self.return_stack[self.rsp]
        elif selector is Selector.PC_IMMEDIATE:
            self.pc = immediate

    def signal_mem_wr(self) -> None:
        assert self.top >= 0, "Data memory underflow"
        assert self.top < self.memory_size, "Data memory overflow"
        self.data_memory[self.top] = self.prev

    def signal_alu_operation(self, operation: ALUOpcode) -> None:
        self.alu.set_details(self.top, self.prev, operation)
        self.alu.calc()

    def signal_output(self) -> None:
        port_num = self.top
        if port_num == 2:
            symbol = chr(self.prev)
            logging.debug(
                "output_symbol_buffer: %s << %s",
                repr("".join(self.output_buffer_symbols)),
                repr(symbol),
            )
            self.output_buffer_symbols.append(symbol)
        elif port_num == 3:
            symbol = self.prev
            logging.debug("output_numeric_buffer: [%s] << %d", ", ".join(map(str, self.output_buffer_nums)), symbol)
            self.output_buffer_nums.append(symbol)

    def signal_latch_top(self, selector: Selector, immediate=0) -> None:
        if selector is Selector.TOP_FROM_PREV:
            self.top = self.prev
        elif selector in [Selector.TOP_FROM_STACK, Selector.TOP_FROM_RETSTACK]:
            self.signal_latch_top_from_stacks(selector)
        elif selector is Selector.TOP_FROM_INPUT:
            self.top = 0
            symbol = self.input_buffer.pop(0)["symbol"]
            self.top = ord(symbol)
            logging.debug("input: %s", repr(symbol))
        elif selector is Selector.TOP_FROM_ALU:
            self.top = self.alu.result
        elif selector is Selector.TOP_FROM_MEM:
            self.top = self.data_memory[self.top]
        elif selector is Selector.TOP_FROM_IMMEDIATE:
            self.top = immediate

    def signal_latch_top_from_stacks(self, selector: Selector) -> None:
        if selector is Selector.TOP_FROM_STACK:
            assert self.sp >= 0, "Data stack underflow"
            assert self.sp < self.return_stack_size, "Data stack overflow"
            self.top = self.data_stack[self.sp]
        elif selector is Selector.TOP_FROM_RETSTACK:
            assert self.rsp >= 0, "Return stack underflow"
            assert self.rsp < self.return_stack_size, "Return stack overflow"
            self.top = self.return_stack[self.rsp]

    def signal_latch_prev(self, selector: Selector) -> None:
        if selector is Selector.PREV_FROM_STACK:
            assert self.sp >= 0, "Data stack underflow"
            assert self.sp < self.data_stack_size, "Data stack overflow"
            self.prev = self.data_stack[self.sp]
        elif selector is Selector.PREV_FROM_TOP:
            self.prev = self.top


def opcode_to_alu_opcode(opcode_type: OpcodeType) -> ALUOpcode | None:
    return {
        OpcodeType.MUL: ALUOpcode.MUL,
        OpcodeType.DIV: ALUOpcode.DIV,
        OpcodeType.SUB: ALUOpcode.SUB,
        OpcodeType.ADD: ALUOpcode.ADD,
        OpcodeType.MOD: ALUOpcode.MOD,
        OpcodeType.EQ: ALUOpcode.EQ,
        OpcodeType.GR: ALUOpcode.GR,
        OpcodeType.LS: ALUOpcode.LS,
    }.get(opcode_type)


class ControlUnit:
    def __init__(self, data_path: DataPath, program_memory_size: int):
        self.data_path = data_path
        self.program_memory_size = program_memory_size
        self.program_memory = [{"index": i, "command": "nop", "arg": 0} for i in range(self.program_memory_size)]
        self.ps = {"Intr_Req": False, "Intr_On": True, "Intr_Mode": False}
        self.tick_number = 0
        self.number_of_instructions = 0

    def fill_memory(self, opcodes: list) -> None:
        for opcode in opcodes:
            mem_cell = int(opcode["index"])
            assert 0 <= mem_cell < self.program_memory_size, "Program index out of memory size"
            self.program_memory[mem_cell] = opcode

    def signal_latch_ps(self, intr_on: bool | None, intr_mode: bool | None) -> None:
        if intr_on is not None:
            self.ps["Intr_On"] = intr_on
        if intr_mode is not None:
            self.ps["Intr_Mode"] = intr_mode

    def go_to_interrupt(self) -> None:
        if self.ps["Intr_Req"] and self.ps["Intr_On"]:
            self.ps["Intr_On"] = False
            self.ps["Intr_Req"] = False
            self.data_path.signal_retstack_wr(Selector.RETSTACK_FROM_PC)
            self.tick()
            self.data_path.signal_latch_pc(Selector.PC_IMMEDIATE, 1)
            self.data_path.signal_latch_rsp(Selector.RSP_INC)
            self.tick()
            self.ps["Intr_Mode"] = True

    def check_for_interruptions(self) -> None:
        if not self.ps["Intr_On"]:
            return
        position = 0
        for index, val in enumerate(self.data_path.input_buffer):
            if val["tick"] > self.tick_number:
                position = index
                break
        self.data_path.input_buffer = self.data_path.input_buffer[0 if position == 0 else position - 1 :]
        if not self.data_path.input_buffer:
            return
        schedule = self.data_path.input_buffer[0]
        if self.tick_number < schedule["tick"]:
            return
        self.ps["Intr_Req"] = True

    def tick(self) -> None:
        self.tick_number += 1

    def command_cycle(self) -> None:
        self.number_of_instructions += 1
        command = self.decode_and_execute_instruction()
        self.check_for_interruptions()

        self.__print__(command)

        if self.ps["Intr_Req"] and self.ps["Intr_On"]:
            logging.warning("Entering into interruption...")
            self.go_to_interrupt()

    def execute(self, memory_cell: dict[str, int | str]) -> None:
        command = OpcodeType(memory_cell["command"])
        arithmetic_operation = opcode_to_alu_opcode(OpcodeType(command))
        if arithmetic_operation is not None:
            self.data_path.signal_alu_operation(arithmetic_operation)
            self.data_path.signal_latch_top(Selector.TOP_FROM_ALU)
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command in [OpcodeType.PUSH, OpcodeType.DROP, OpcodeType.SWAP, OpcodeType.OVER, OpcodeType.DUP]:
            self.execute_basic_op(memory_cell)
        elif command in [
            OpcodeType.LOAD,
            OpcodeType.STORE,
            OpcodeType.POP,
            OpcodeType.RPOP,
            OpcodeType.EMIT,
            OpcodeType.READ,
        ]:
            self.execute_mem_stacks_io_op(memory_cell)
        elif command in [OpcodeType.ZJMP, OpcodeType.JMP, OpcodeType.CALL, OpcodeType.RET]:
            self.execute_jumps_op(memory_cell)
        elif command == OpcodeType.DI:
            self.signal_latch_ps(intr_on=False, intr_mode=None)
            self.tick()
        elif command == OpcodeType.EI:
            self.signal_latch_ps(intr_on=True, intr_mode=None)
            self.tick()

    def execute_basic_op(self, memory_cell: dict[str, int | str]) -> None:
        command = OpcodeType(memory_cell["command"])
        if command == OpcodeType.PUSH:
            self.data_path.signal_stack_wr(Selector.STACK_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_TOP)
            self.data_path.signal_latch_top(Selector.TOP_FROM_IMMEDIATE, memory_cell["arg"])
            self.data_path.signal_latch_sp(Selector.SP_INC)
            self.tick()
        elif command == OpcodeType.DROP:
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.SWAP:
            self.data_path.signal_stack_wr(Selector.STACK_FROM_TOP)
            self.data_path.signal_latch_top(Selector.TOP_FROM_PREV)
            self.tick()
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.OVER:
            self.data_path.signal_stack_wr(Selector.STACK_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_TOP)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_STACK)
            self.data_path.signal_latch_sp(Selector.SP_INC)
            self.tick()
        elif command == OpcodeType.DUP:
            self.data_path.signal_stack_wr(Selector.STACK_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_TOP)
            self.data_path.signal_latch_sp(Selector.SP_INC)
            self.tick()

    def execute_mem_stacks_io_op(self, memory_cell: dict[str, int | str]) -> None:
        command = OpcodeType(memory_cell["command"])
        if command == OpcodeType.LOAD:
            self.data_path.signal_latch_top(Selector.TOP_FROM_MEM)
            self.tick()
        elif command == OpcodeType.STORE:
            self.data_path.signal_mem_wr()
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_STACK)
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.POP:
            self.data_path.signal_retstack_wr(Selector.RETSTACK_FROM_TOP)
            self.data_path.signal_latch_rsp(Selector.RSP_INC)
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.RPOP:
            self.data_path.signal_stack_wr(Selector.STACK_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_TOP)
            self.data_path.signal_latch_sp(Selector.SP_INC)
            self.data_path.signal_latch_rsp(Selector.RSP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_RETSTACK)
            self.tick()
        elif command == OpcodeType.EMIT:
            self.data_path.signal_output()
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_STACK)
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.READ:
            self.data_path.signal_latch_top(Selector.TOP_FROM_INPUT)
            self.tick()

    def execute_jumps_op(self, memory_cell: dict[str, int | str]) -> None:
        command = OpcodeType(memory_cell["command"])
        if command == OpcodeType.ZJMP:
            if self.data_path.top == 0:
                self.data_path.signal_latch_pc(Selector.PC_IMMEDIATE, memory_cell["arg"])
            self.data_path.signal_latch_sp(Selector.SP_DEC)
            self.tick()
            self.data_path.signal_latch_top(Selector.TOP_FROM_PREV)
            self.data_path.signal_latch_prev(Selector.PREV_FROM_STACK)
            self.tick()
        elif command == OpcodeType.JMP:
            self.data_path.signal_latch_pc(Selector.PC_IMMEDIATE, memory_cell["arg"])
            self.tick()
        elif command == OpcodeType.CALL:
            self.data_path.signal_retstack_wr(Selector.RETSTACK_FROM_PC)
            self.data_path.signal_latch_pc(Selector.PC_IMMEDIATE, memory_cell["arg"])
            self.data_path.signal_latch_rsp(Selector.RSP_INC)
            self.tick()
        elif command == OpcodeType.RET:
            self.data_path.signal_latch_rsp(Selector.RSP_DEC)
            self.tick()
            self.data_path.signal_latch_pc(Selector.PC_RET)
            self.signal_latch_ps(intr_mode=False, intr_on=None)
            self.tick()

    def decode_and_execute_instruction(self) -> str:
        memory_cell = self.program_memory[self.data_path.pc]
        self.data_path.signal_latch_pc(Selector.PC_INC)
        self.tick()

        if memory_cell["command"] == OpcodeType.HALT:
            raise StopIteration

        self.execute(memory_cell)
        return memory_cell["command"] + " " + str(memory_cell.get("arg", ""))

    def __print__(self, command: str) -> None:
        tos_memory = [
            self.data_path.data_stack[i] for i in range(self.data_path.sp - 1, self.data_path.sp - 4, -1) if i >= 0
        ]
        tos = [self.data_path.top, self.data_path.prev, *tos_memory]
        ret_tos = self.data_path.return_stack[self.data_path.rsp - 1 : self.data_path.rsp - 4 : -1]
        state_repr = (
            "{:4} | TICK: {:4} | INSTR: {:7} | PC: {:3} | PS_REQ {:1} | PS_MODE: {:1} | SP: {:3} | RSP: "
            "{:3} | DATA_MEMORY[TOP] {:7} | TOS : {} | RETURN_TOS : {}"
        ).format(
            "INTR" if self.ps["Intr_Mode"] else "MAIN",
            self.tick_number,
            command,
            self.data_path.pc,
            self.ps["Intr_Req"],
            self.ps["Intr_On"],
            self.data_path.sp,
            self.data_path.rsp,
            self.data_path.data_memory[self.data_path.top] if self.data_path.top < self.data_path.memory_size else "?",
            str(tos),
            str(ret_tos),
        )
        logging.info(state_repr)


def parse_to_tokens(input_file: str) -> list:
    tokens = []
    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        if not input_text:
            input_token = []
        else:
            input_token = eval(input_text)

    if len(input_token) > 0:
        for tick, symbol in input_token:
            tokens.append({"tick": tick, "symbol": symbol})
    return tokens


def simulation(code: list, limit: int, input_tokens: list[tuple]) -> list[list, list, int, int]:
    data_path = DataPath(15000, 15000, 15000, input_tokens)
    control_unit = ControlUnit(data_path, 15000)
    control_unit.fill_memory(code)
    while control_unit.tick_number < limit:
        try:
            control_unit.command_cycle()
        except StopIteration:
            break

    return [
        control_unit.data_path.output_buffer_symbols,
        control_unit.data_path.output_buffer_nums,
        control_unit.number_of_instructions,
        control_unit.tick_number,
    ]


def main(code_path: str, token_path: str | None) -> None:
    input_tokens = []
    if token_path is not None:
        input_tokens = parse_to_tokens(token_path)

    code = read_code(code_path)
    symbols, nums, instr_num, ticks = simulation(
        code,
        limit=7000,
        input_tokens=input_tokens,
    )
    print(
        f"Output Symbols: {''.join(symbols)}\nOutput Numbers: {nums}\nInstruction number: {instr_num!s}\nTicks: {ticks - 1!s}"
    )


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert 2 <= len(sys.argv) <= 3, "Wrong arguments: machine.py <code_file> [<input_file>]"
    if len(sys.argv) == 3:
        _, code_file, input_file = sys.argv
    else:
        _, code_file = sys.argv
        input_file = None
    main(code_file, input_file)
