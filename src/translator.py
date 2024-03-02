from __future__ import annotations

import shlex
import sys

import pytest

from isa import Opcode, OpcodeParam, OpcodeParamType, OpcodeType, TermType, write_code

variables = {}
functions = {}
variable_current_address = 512
string_current_address = 0


class Term:
    def __init__(self, word_number: int, term_type: TermType | None, word: str):
        self.operand = None
        self.word_number = word_number
        self.term_type = term_type
        self.word = word
        self.converted = False


def word_to_term(word: str) -> Term | None:
    return {
        "di": TermType.DI,
        "ei": TermType.EI,
        "dup": TermType.DUP,
        "+": TermType.ADD,
        "-": TermType.SUB,
        "*": TermType.MUL,
        "/": TermType.DIV,
        "mod": TermType.MOD,
        "emit": TermType.EMIT,
        "read": TermType.READ,
        "swap": TermType.SWAP,
        "drop": TermType.DROP,
        "over": TermType.OVER,
        "=": TermType.EQ,
        "<": TermType.LS,
        ">": TermType.GR,
        "variable": TermType.VARIABLE,
        "allot": TermType.ALLOT,
        "!": TermType.STORE,
        "@": TermType.LOAD,
        "if": TermType.IF,
        "else": TermType.ELSE,
        "then": TermType.THEN,
        ":": TermType.DEF,
        ";": TermType.RET,
        ":intr": TermType.DEF_INTR,
        "begin": TermType.BEGIN,
        "until": TermType.UNTIL,
    }.get(word)


def read_lines(data: str) -> list[str]:
    code = shlex.split(data.replace("\n", " "), posix=True)
    return list(filter(lambda x: len(x) > 0, code))


def remove_comments(code_lines: list[str]) -> list[str]:
    without_comments = []
    for line in code_lines:
        index = line.find("#")
        if index == -1:
            without_comments.append(line)
            continue
        line = line[0 : line.find("#")].strip()
        if line != "":
            without_comments.append(line)
    return without_comments


def words2terms(source_code: list[str]) -> list[Term]:
    terms = [Term(0, TermType.ENTRYPOINT, "")]
    for word_number, word in enumerate(source_code):
        term_type = word_to_term(word)
        if word[:2] == ". ":
            word = f'."{word[2:]}"'
            term_type = TermType.STRING
        terms.append(Term(word_number + 1, term_type, word))
    return terms


def set_if_else_then(terms: list[Term]) -> None:
    nested_ifs = []
    for term_index, term in enumerate(terms):
        if term.term_type is TermType.IF:
            nested_ifs.append(term)
        elif term.term_type is TermType.ELSE:
            nested_ifs.append(term)
        elif term.term_type is TermType.THEN:
            assert len(nested_ifs) > 0, "IF-ELSE-THEN unbalanced at word #" + str(term.word_number)
            last_if = nested_ifs.pop()
            if last_if.term_type is TermType.ELSE:
                last_else = last_if
                assert len(nested_ifs) > 0, "IF-ELSE-THEN unbalanced at word #" + str(term.word_number)
                last_if = nested_ifs.pop()
                last_else.operand = term.word_number + 1
                last_if.operand = last_else.word_number + 1
            else:
                last_if.operand = term.word_number + 1

    assert len(nested_ifs) == 0, "IF-ELSE-THEN unbalanced at word #" + str(nested_ifs[0].word_number)


def replace_vars_and_funcs(terms: list[Term]) -> None:
    for term_index, term in enumerate(terms):
        if term.term_type is None and not term.converted:
            if term.word in variables:
                term.word = str(variables[term.word])
    for term_index, term in enumerate(terms):
        if term.term_type is None and not term.converted:
            if term.word in functions.keys():
                term.operand = functions[term.word]
                term.term_type = TermType.CALL
                term.word = "call"


def set_allot_for_variable(terms: list[Term], term_index: int) -> None:
    global variable_current_address
    term = terms[term_index]
    if term.term_type is TermType.ALLOT:
        assert term_index - 3 >= 0, "Bad allot declaration at the beginning of the file #" + str(term.word_number)
        terms[term_index - 1].converted = True
        try:
            allot_size = int(terms[term_index - 1].word)
            assert 1 <= allot_size <= 100, "Incorrect allot size at word #" + str(term.word_number - 1)
            variable_current_address += allot_size
        except ValueError:
            pytest.fail("Incorrect allot size at word #" + str(term.word_number - 1))


def set_variables(terms: list[Term]) -> None:
    global variable_current_address
    for term_index, term in enumerate(terms):
        # variable <name> [<size> allot]
        if term.term_type is TermType.VARIABLE:
            assert term_index + 1 < len(terms), "Bad variable declaration at the end of the file" + str(
                term.word_number
            )
            assert terms[term_index + 1].term_type is None, "Variable name same as the key word at #" + str(
                term.word_number + 1
            )
            assert terms[term_index + 1].word[0].isalpha(), "Bad variable name at word #" + str(term.word_number + 1)
            assert terms[term_index + 1] not in variables, "Variable already exists at word #" + str(
                term.word_number + 1
            )
            variables[terms[term_index + 1].word] = variable_current_address
            variable_current_address += 1
            terms[term_index + 1].converted = True
            if term_index + 3 < len(terms) and terms[term_index + 3].term_type is TermType.ALLOT:
                set_allot_for_variable(terms, term_index + 3)


def set_functions(terms: list[Term]) -> None:
    global functions
    func_indexes_stack = []
    for term_index, term in enumerate(terms):
        if term.term_type is TermType.DEF or term.term_type is TermType.DEF_INTR:
            assert term_index + 1 < len(terms), "Missed function name at the end of the file" + str(term.word_number)
            assert len(func_indexes_stack) == 0, "Unclosed function (nested functions not allowed) at word # " + str(
                term.word_number
            )
            assert term.word not in functions, "Duplicate function at word # " + str(term.word_number)
            func_indexes_stack.append(term.word_number)
            func_name = terms[term_index + 1].word
            functions[func_name] = term.word_number + 1
            terms[term_index + 1].converted = True
        if term.term_type == TermType.RET:
            assert len(func_indexes_stack) >= 1, "RET out of function at word # " + str(term.word_number)
            function_term = terms[func_indexes_stack.pop()]
            function_term.operand = term.word_number + 1
    assert len(func_indexes_stack) == 0, "Unclosed function"


def check_begin_until(terms: list[Term]) -> None:
    nested = []
    for term_index, term in enumerate(terms):
        if term.term_type is TermType.BEGIN:
            nested.append(term.word_number)
        if term.term_type == TermType.UNTIL:
            assert len(nested) > 0, "Unbalanced begin ... until at word #" + str(term.word_number)
            term.operand = nested.pop()
    assert len(nested) == 0, "Unbalanced begin ... until"


def validate(terms: list[Term]):
    check_begin_until(terms)
    set_functions(terms)
    set_variables(terms)
    replace_vars_and_funcs(terms)
    set_if_else_then(terms)


def fix_interrupt_function(terms: list[Term]) -> list[Term]:
    is_interrupt = False
    interrupt_ret = 1
    terms_interrupt_proc = []
    terms_not_interrupt_proc = []
    for term in terms[1:]:
        if term.term_type is TermType.DEF_INTR:
            is_interrupt = True
        if term.term_type is TermType.RET:
            if is_interrupt:
                terms_interrupt_proc.append(term)
                interrupt_ret = len(terms_interrupt_proc) + 1
            else:
                terms_not_interrupt_proc.append(term)
            is_interrupt = False

        if is_interrupt:
            terms_interrupt_proc.append(term)
        elif not is_interrupt and term.term_type is not TermType.RET:
            terms_not_interrupt_proc.append(term)

    terms[0].operand = interrupt_ret
    return [*[terms[0]], *terms_interrupt_proc, *terms_not_interrupt_proc]


def fix_literal_term(term: Term) -> list[Opcode]:
    global string_current_address
    if term.converted:
        opcodes = []
    elif term.term_type is not TermType.STRING:
        opcodes = [Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, term.word)])]
    else:
        opcodes = []
        content = term.word[2:-1]  # ." <content>"
        string_start = string_current_address
        opcodes.append(Opcode(OpcodeType.POP, []))  # Сохранить временно номер порта буфер - output port
        for char in content:
            opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, ord(char))]))
            opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, string_current_address)]))
            opcodes.append(Opcode(OpcodeType.STORE, []))
            string_current_address += 1

        opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, 0)]))
        opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, string_current_address)]))

        opcodes.append(Opcode(OpcodeType.STORE, []))
        string_current_address += 1

        opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, string_start)]))

        opcodes.append(Opcode(OpcodeType.DUP, []))  # JMP
        opcodes.append(Opcode(OpcodeType.LOAD, []))
        opcodes.append(Opcode(OpcodeType.DUP, []))
        opcodes.append(Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.ADDR_REL, 8)]))
        opcodes.append(Opcode(OpcodeType.RPOP, []))  # output port
        opcodes.append(Opcode(OpcodeType.DUP, []))  # output port
        opcodes.append(Opcode(OpcodeType.POP, []))  # output port
        opcodes.append(Opcode(OpcodeType.EMIT, []))
        opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, 1)]))
        opcodes.append(Opcode(OpcodeType.ADD, []))
        opcodes.append(Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.ADDR_REL, -10)]))
        opcodes.append(Opcode(OpcodeType.DROP, []))  # ZJMP
        opcodes.append(Opcode(OpcodeType.DROP, []))

    return opcodes


def term_to_opcodes(term: Term) -> list[Opcode]:
    opcodes = {
        TermType.DI: [Opcode(OpcodeType.DI, [])],
        TermType.EI: [Opcode(OpcodeType.EI, [])],
        TermType.DUP: [Opcode(OpcodeType.DUP, [])],
        TermType.ADD: [Opcode(OpcodeType.ADD, [])],
        TermType.SUB: [Opcode(OpcodeType.SUB, [])],
        TermType.MUL: [Opcode(OpcodeType.MUL, [])],
        TermType.DIV: [Opcode(OpcodeType.DIV, [])],
        TermType.MOD: [Opcode(OpcodeType.MOD, [])],
        TermType.EMIT: [Opcode(OpcodeType.EMIT, [])],
        TermType.SWAP: [Opcode(OpcodeType.SWAP, [])],
        TermType.DROP: [Opcode(OpcodeType.DROP, [])],
        TermType.OVER: [Opcode(OpcodeType.OVER, [])],
        TermType.EQ: [Opcode(OpcodeType.EQ, [])],
        TermType.LS: [Opcode(OpcodeType.LS, [])],
        TermType.GR: [Opcode(OpcodeType.GR, [])],
        TermType.READ: [Opcode(OpcodeType.READ, [])],
        TermType.VARIABLE: [],
        TermType.ALLOT: [],
        TermType.STORE: [Opcode(OpcodeType.STORE, [])],
        TermType.LOAD: [Opcode(OpcodeType.LOAD, [])],
        TermType.IF: [Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
        TermType.ELSE: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
        TermType.THEN: [],
        TermType.DEF: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
        TermType.RET: [Opcode(OpcodeType.RET, [])],
        TermType.DEF_INTR: [],
        TermType.BEGIN: [],
        TermType.UNTIL: [Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
        TermType.CALL: [Opcode(OpcodeType.CALL, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
        TermType.ENTRYPOINT: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
    }.get(term.term_type)

    if term.operand and opcodes is not None:
        for opcode in opcodes:
            for param_num, param in enumerate(opcode.params):
                if param.param_type is OpcodeParamType.UNDEFINED:
                    opcode.params[param_num].param_type = OpcodeParamType.ADDR
                    opcode.params[param_num].value = term.operand

    if opcodes is None:
        return fix_literal_term(term)

    return opcodes


def fix_addresses_in_opcodes(term_opcodes: list[list[Opcode]]) -> list[Opcode]:
    result_opcodes = []
    pref_sum = [0]
    for term_num, opcodes in enumerate(term_opcodes):
        term_opcode_cnt = len(opcodes)
        pref_sum.append(pref_sum[term_num] + term_opcode_cnt)
    for term_opcode in list(filter(lambda x: x is not None, term_opcodes)):
        for opcode in term_opcode:
            for param_num, param in enumerate(opcode.params):
                if param.param_type is OpcodeParamType.ADDR:
                    opcode.params[param_num].value = pref_sum[param.value]
                    opcode.params[param_num].param_type = OpcodeParamType.CONST
                if param.param_type is OpcodeParamType.ADDR_REL:
                    opcode.params[param_num].value = len(result_opcodes) + opcode.params[param_num].value
                    opcode.params[param_num].param_type = OpcodeParamType.CONST
            result_opcodes.append(opcode)
    return result_opcodes


def terms_to_opcodes(terms: list[Term]) -> list[Opcode]:
    terms = fix_interrupt_function(terms)
    opcodes = list(map(term_to_opcodes, terms))
    opcodes = fix_addresses_in_opcodes(opcodes)
    return [*opcodes, Opcode(OpcodeType.HALT, [])]


def translate(data: str) -> list[dict]:
    lines = read_lines(data)
    lines = remove_comments(lines)
    terms = words2terms(lines)
    validate(terms)
    opcodes = terms_to_opcodes(terms)
    commands = []
    for index, opcode in enumerate(opcodes):
        command = {
            "index": index,
            "command": opcode.opcode_type,
        }
        try:
            if len(opcode.params):
                command["arg"] = int(opcode.params[0].value)
        except Exception:
            pytest.fail("Error: String value given as an operand:" + opcode.params[0].value)
        commands.append(command)
    return commands


def main(source_file: str, target_file: str):
    global variables, functions, variable_current_address, string_current_address

    variables = {}
    functions = {}
    variable_current_address = 512
    string_current_address = 0

    with open(source_file) as file:
        data = file.read()
    commands = translate(data)
    write_code(target_file, commands)
    print("source LoC:", len(data.split("\n")), "code instr:", len(commands))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, source, target = sys.argv
    main(source, target)
