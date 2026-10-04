"""Bounded, explicitly authored arithmetic policies; never Python eval or prose execution."""
import ast
import hashlib
import json
import math
import operator
import re

FEATURES = {'bsc_gain', 'bsc_loss', 'bsc_conditional_gain', 'bsc_conditional_loss',
            'forecast_ts1', 'warning_count', 'penalty_total', 'precedent_share', 'production'}
FUNCTIONS = {'min', 'max', 'abs', 'round', 'clamp'}
ALLOWED = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
           ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Not,
           ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq,
           ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.IfExp, ast.Call)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def number(value):
    if value is None or isinstance(value, bool):
        raise ValueError('ranking requires a known numeric value')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('ranking requires a numeric value') from exc
    if not math.isfinite(result):
        raise ValueError('ranking requires finite numeric values')
    return result


def truth(value):
    if type(value) is not bool:
        raise ValueError('ranking condition requires a boolean, not truthiness')
    return value


def compile_expression(text, names):
    if not isinstance(text, str) or not 1 <= len(text) <= 2048:
        raise ValueError('ranking expression must contain 1..2048 characters')
    try:
        tree = ast.parse(text, mode='eval')
    except (SyntaxError, RecursionError) as exc:
        raise ValueError('invalid ranking expression') from exc
    nodes = list(ast.walk(tree))
    callees = {id(node.func) for node in nodes if isinstance(node, ast.Call)}
    if len(nodes) > 256:
        raise ValueError('ranking expression is too complex')
    def depth(node):
        return 1 + max((depth(n) for n in ast.iter_child_nodes(node)), default=0)
    if depth(tree) > 32:
        raise ValueError('ranking expression is too deep')
    for node in nodes:
        if not isinstance(node, ALLOWED):
            raise ValueError(f'unsupported ranking expression: {type(node).__name__}')
        if isinstance(node, ast.Name) and node.id not in names | FUNCTIONS:
            raise ValueError(f'unknown ranking input: {node.id}')
        if isinstance(node, ast.Name) and node.id in FUNCTIONS and id(node) not in callees:
            raise ValueError('ranking functions must be called')
        if isinstance(node, ast.Constant):
            if node.value is not None and type(node.value) not in (str, bool, int, float):
                raise ValueError('unsupported ranking literal')
            if isinstance(node.value, str) and len(node.value) > 128:
                raise ValueError('ranking literal is too long')
            if type(node.value) in (int, float):
                number(node.value)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
                raise ValueError('unsupported ranking function')
            n = len(node.args)
            bounds = {'min':(2,8),'max':(2,8),'abs':(1,1),'round':(2,2),'clamp':(3,3)}[node.func.id]
            if not bounds[0] <= n <= bounds[1]:
                raise ValueError('invalid ranking function arguments')
    return tree


def validate(value):
    if isinstance(value, str):
        if len(value) > 32000:
            raise ValueError('ranking policy is too large')
        try:
            value = json.loads(value)
        except (ValueError, RecursionError) as exc:
            raise ValueError('invalid ranking policy JSON') from exc
    if not isinstance(value, dict) or set(value) != {'version','inputs','components','tieBreak'}:
        raise ValueError('ranking policy requires version, inputs, components and tieBreak')
    if type(value['version']) is not int or value['version'] != 1 or value['tieBreak'] != 'lower_approver':
        raise ValueError('unsupported ranking policy version or tieBreak')
    inputs, components = value['inputs'], value['components']
    if not isinstance(inputs, dict) or len(inputs)>32 or not isinstance(components, dict) or not 1<=len(components)<=16:
        raise ValueError('ranking requires up to32 inputs and 1..16 components')
    for key in inputs.keys() | components.keys():
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',key):
            raise ValueError('invalid ranking input/component name')
    if inputs.keys() & (FEATURES | FUNCTIONS):
        raise ValueError('ranking aliases must not shadow built-in features/functions')
    if any(not isinstance(v,str) or not v or len(v)>160 for v in inputs.values()):
        raise ValueError('ranking inputs must name explicit fact variables')
    for expression in components.values():
        compile_expression(expression, FEATURES | inputs.keys())
    return json.loads(canonical(value))


def evaluate_expression(text, context):
    tree = compile_expression(text, set(context))
    def run(node):
        if isinstance(node,ast.Expression): return run(node.body)
        if isinstance(node,ast.Constant): return node.value
        if isinstance(node,ast.Name):
            if node.id not in context: raise ValueError('function names are not values')
            return context[node.id]
        if isinstance(node,ast.IfExp): return run(node.body if truth(run(node.test)) else node.orelse)
        if isinstance(node,ast.BoolOp):
            for part in node.values:
                value=truth(run(part))
                if isinstance(node.op,ast.And) and not value: return False
                if isinstance(node.op,ast.Or) and value: return True
            return isinstance(node.op,ast.And)
        if isinstance(node,ast.UnaryOp):
            value=run(node.operand)
            if isinstance(node.op,ast.Not): return not truth(value)
            return number(value) * (-1 if isinstance(node.op,ast.USub) else 1)
        if isinstance(node,ast.BinOp):
            a,b=number(run(node.left)),number(run(node.right))
            try: result={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}[type(node.op)](a,b)
            except (ArithmeticError,OverflowError) as exc: raise ValueError('invalid ranking arithmetic') from exc
            return number(result)
        if isinstance(node,ast.Compare):
            a=run(node.left)
            for op,right in zip(node.ops,node.comparators):
                b=run(right)
                if isinstance(op,(ast.Is,ast.IsNot)):
                    if a is not None and b is not None: raise ValueError('ranking is/is not only supports None')
                    hit=(a is b) if isinstance(op,ast.Is) else (a is not b)
                else:
                    if a is None or b is None: raise ValueError('ranking comparison input is unknown')
                    if isinstance(a,bool) or isinstance(b,bool):
                        if type(a) is not bool or type(b) is not bool or not isinstance(op,(ast.Eq,ast.NotEq)):
                            raise ValueError('ranking boolean types must match')
                    elif not (isinstance(a,str) and isinstance(b,str)):
                        a,b=number(a),number(b)
                    hit={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge}[type(op)](a,b)
                if not hit: return False
                a=b
            return True
        if isinstance(node,ast.Call):
            values=[number(run(arg)) for arg in node.args]; name=node.func.id
            if name=='min': return min(values)
            if name=='max': return max(values)
            if name=='abs': return abs(values[0])
            if name=='round':
                if values[1]!=int(values[1]) or not 0<=values[1]<=10: raise ValueError('round precision must be 0..10')
                return round(values[0],int(values[1]))
            if values[1]>values[2]: raise ValueError('invalid clamp bounds')
            return max(values[1],min(values[2],values[0]))
        raise ValueError('unsupported ranking node')
    return run(tree)


def calculate(text, context):
    return number(evaluate_expression(text, context))


def predicate(text, context):
    return truth(evaluate_expression(text, context))


def score(policy, features, facts):
    policy=validate(policy)
    context=dict(features, **{alias:facts.get(var) for alias,var in policy['inputs'].items()})
    parts={key:round(calculate(expr,context),2) for key,expr in policy['components'].items()}
    return {'score':round(number(sum(parts.values())),2),'scoreParts':parts}
