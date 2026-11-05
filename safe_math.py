"""Safe arithmetic evaluator used by the `calculate` command.

Only numbers, parentheses and the operators + - * / // % ** are allowed.
Anything else (names, function calls, attribute access, strings...) is rejected,
so user input can never run Python code.
"""
import ast
import math
import operator

MAX_EXPRESSION_LENGTH = 200
MAX_RESULT_DIGITS = 1000

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalcError(ValueError):
    """Raised when an expression is invalid or too big to compute."""


def _check_size(value):
    if isinstance(value, int) and value != 0:
        if math.log10(abs(value)) > MAX_RESULT_DIGITS:
            raise CalcError("Result is too big.")
    return value


def _check_power(base, exponent):
    if abs(exponent) > MAX_RESULT_DIGITS:
        raise CalcError("Exponent is too big.")
    if abs(base) > 1 and exponent > 0:
        if exponent * math.log10(abs(base)) > MAX_RESULT_DIGITS:
            raise CalcError("Result is too big.")


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalcError("Only numbers are allowed.")
        return node.value

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow):
            _check_power(left, right)
        try:
            result = _BIN_OPS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise CalcError("Division by zero.")
        except OverflowError:
            raise CalcError("Result is too big.")
        if isinstance(result, complex):
            raise CalcError("Complex results are not supported.")
        return _check_size(result)

    raise CalcError("Only numbers and + - * / // % ** ( ) are allowed.")


def safe_calculate(expression: str):
    """Evaluate a plain arithmetic expression and return the number."""
    expression = expression.strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    if not expression:
        raise CalcError("Empty expression.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalcError(f"Expression is too long (max {MAX_EXPRESSION_LENGTH} characters).")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise CalcError("Invalid expression.")
    result = _eval(tree)
    if isinstance(result, float):
        if math.isnan(result) or math.isinf(result):
            raise CalcError("Result is not a finite number.")
        if result.is_integer() and abs(result) < 1e15:
            return int(result)
    return result
