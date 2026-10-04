"""Validated ontology pattern definitions. This module never evaluates Python code."""
import ast
from dataclasses import dataclass
import hashlib
import json
import math
import operator
import re

from hydcommon.daq_contract import ALWAYS, AUX, DEADBAND, reporting_interval

TAGS = ALWAYS | AUX | set(DEADBAND)
OPS = {ast.Gt: ('>', operator.gt), ast.GtE: ('>=', operator.ge),
       ast.Lt: ('<', operator.lt), ast.LtE: ('<=', operator.le),
       ast.Eq: ('==', operator.eq), ast.NotEq: ('!=', operator.ne)}
VARIABLES = ({tag.lower(): tag for tag in TAGS}
             | {f'{tag.lower()}_slope': f'slope({tag})' for tag in TAGS}
             | {'load': 'LoadSP', 'plc_state': 'PLC_STATE'})


class DefinitionError(ValueError):
    pass


class Expression:
    """Boolean comparisons, and/or/not, and slope(TAG); explicit closed grammar."""
    def __init__(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 2048:
            raise DefinitionError('condition must contain 1..2048 characters')
        try:
            tree = ast.parse(text, mode='eval')
        except (SyntaxError, RecursionError) as exc:
            raise DefinitionError('invalid condition syntax') from exc
        if sum(1 for _ in ast.walk(tree)) > 128:
            raise DefinitionError('condition is too complex')
        self.text, self.inputs, self.slopes, self.atoms = text, set(), set(), []
        self.node = self._compile(tree.body, 0)

    def _term(self, node):
        if isinstance(node, ast.Name) and node.id in TAGS:
            self.inputs.add(node.id)
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'PLC' and node.attr == 'state':
            self.inputs.add('PLC_STATE')
            return 'PLC_STATE'
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'slope'
                and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Name)
                and node.args[0].id in TAGS):
            tag = node.args[0].id
            self.inputs.add(tag); self.slopes.add(tag)
            return f'slope({tag})'
        raise DefinitionError('unsupported input or function')

    def _compile(self, node, depth):
        if depth > 12:
            raise DefinitionError('condition nesting is too deep')
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return ('and' if isinstance(node.op, ast.And) else 'or', tuple(self._compile(n, depth+1) for n in node.values))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return ('not', self._compile(node.operand, depth+1))
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or type(node.ops[0]) not in OPS:
            raise DefinitionError('expected a supported comparison')
        term = self._term(node.left)
        rhs = node.comparators[0]
        sign = 1
        if isinstance(rhs, ast.UnaryOp) and isinstance(rhs.op, (ast.USub, ast.UAdd)):
            sign = -1 if isinstance(rhs.op, ast.USub) else 1
            rhs = rhs.operand
        if not isinstance(rhs, ast.Constant):
            raise DefinitionError('comparison value must be a literal')
        value = rhs.value
        if term == 'PLC_STATE':
            if value not in ('RUN', 'STOP', 'TRIP') or sign != 1 or type(node.ops[0]) not in (ast.Eq, ast.NotEq):
                raise DefinitionError('PLC state requires == or != RUN/STOP/TRIP')
        elif type(value) not in (int, float) or not math.isfinite(value):
            raise DefinitionError('sensor comparison requires a finite number')
        else:
            value = float(value) * sign
        op = OPS[type(node.ops[0])][0]
        self.atoms.append((term, op, value))
        return ('compare', term, type(node.ops[0]), value)

    def evaluate(self, values, slopes):
        # Check every input before short circuiting: a missing branch is unknown.
        for tag in self.inputs:
            value = values[tag]
            if tag == 'PLC_STATE':
                if value not in ('RUN', 'STOP', 'TRIP'):
                    raise ValueError('invalid PLC state')
            elif type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError('invalid measurement')
        for tag in self.slopes:
            if type(slopes[tag]) not in (float, int) or not math.isfinite(slopes[tag]):
                raise ValueError('invalid slope')
        def run(node):
            if node[0] == 'and': return all(run(n) for n in node[1])
            if node[0] == 'or': return any(run(n) for n in node[1])
            if node[0] == 'not': return not run(node[1])
            _, term, op, expected = node
            actual = slopes[term[6:-1]] if term.startswith('slope(') else values[term]
            return OPS[op][1](actual, expected)
        return run(self.node)


def positive_number(row, key):
    n = row.get(key)
    if type(n) not in (int, float) or not math.isfinite(n) or not 0 < n <= 86400:
        raise DefinitionError(f'{key} must be finite and in (0, 86400]')
    return float(n)


@dataclass(frozen=True)
class Pattern:
    id: str
    code: str
    severity: str
    summary: str
    rule: Expression
    clear: Expression
    hold: float
    clear_hold: float
    slope_window: float
    revision: str

    @property
    def inputs(self):
        return self.rule.inputs | self.clear.inputs

    @property
    def slopes(self):
        return self.rule.slopes | self.clear.slopes

    def validate_reporting(self, profile, time_scale):
        if type(time_scale) not in (int, float) or not math.isfinite(time_scale) or time_scale <= 0:
            raise DefinitionError('time scale must be finite and positive')
        for tag in self.inputs - {'PLC_STATE'}:
            if reporting_interval(tag, profile) != 1:
                raise DefinitionError(f'{tag}: temporal input requires periodic 1 Hz reporting; use full or update DAQ contract')
        for tag in self.slopes:
            if self.slope_window < 2 * reporting_interval(tag, profile) * time_scale:
                raise DefinitionError(f'{tag}: slope window requires at least two reporting intervals')

    def describe(self):
        return dict(id=self.id, code=self.code, severity=self.severity, rule=self.summary, condition=self.rule.text,
                    clearRule=self.clear.text, holdSeconds=self.hold, clearHoldSeconds=self.clear_hold,
                    slopeWindowSeconds=self.slope_window, revision=self.revision,
                    inputs=sorted(self.inputs), slopes=sorted(self.slopes))

    def source(self):
        variables = {term: variable for variable, term in VARIABLES.items()}
        return self.describe() | dict(detectionMode='held', tests=[
            dict(variable=variables[term], operator=op, value=value) for term, op, value in self.rule.atoms])


def compile_pattern(row):
    if not isinstance(row, dict) or row.get('detectionMode') != 'held':
        raise DefinitionError('detectionMode must be held; PLC trips use the authoritative PLC watcher')
    if not isinstance(row.get('id'), str) or not row['id'] or len(row['id']) > 160:
        raise DefinitionError('pattern id is required')
    if not isinstance(row.get('code'), str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,79}', row['code']):
        raise DefinitionError('invalid pattern code')
    if row.get('severity') not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
        raise DefinitionError('invalid severity')
    # schema.json defines rule as human-readable summary, TESTS as AND predicates.
    # Never silently promote prose into executable code or infer predicates from it.
    summary = row.get('rule')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 4096:
        raise DefinitionError('human-readable rule summary is required')
    clear = Expression(row.get('clearRule'))
    tests = row.get('tests')
    if not isinstance(tests, list) or not tests:
        raise DefinitionError('TESTS input/threshold catalog is required')
    expected = []
    for test in tests:
        if not isinstance(test, dict) or test.get('variable') not in VARIABLES:
            raise DefinitionError('unsupported TESTS InputData.variable')
        value = test.get('value')
        if type(value) not in (int, float, str) or isinstance(value, float) and not math.isfinite(value):
            raise DefinitionError('invalid TESTS value')
        if type(value) in (int, float):
            value = float(value)
        expected.append((VARIABLES[test['variable']], test.get('operator'), value))
    key = lambda item: (item[0], item[1], str(item[2]))
    if any(op not in {entry[0] for entry in OPS.values()} for _, op, _ in expected):
        raise DefinitionError('unsupported TESTS operator')
    if len(expected) > 32 or len(expected) != len(set(expected)):
        raise DefinitionError('TESTS must have at most 32 unique comparisons')
    def source_term(term):
        return 'PLC.state' if term == 'PLC_STATE' else term
    rule = Expression(' and '.join(f'{source_term(term)} {op} {json.dumps(value)}'
                                   for term, op, value in sorted(expected, key=key)))
    hold = positive_number(row, 'holdSeconds')
    clear_hold = positive_number(row, 'clearHoldSeconds')
    window = positive_number(row, 'slopeWindowSeconds')
    canonical = dict(id=row['id'], code=row['code'], severity=row['severity'], rule=summary, condition=rule.text,
                     clearRule=clear.text, holdSeconds=hold, clearHoldSeconds=clear_hold,
                     slopeWindowSeconds=window, tests=sorted(expected, key=key))
    revision = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return Pattern(row['id'], row['code'], row['severity'], summary, rule, clear, hold, clear_hold, window, revision)


def compile_catalog(rows, profile='lite', time_scale=20):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise DefinitionError('catalog must contain 1..64 held patterns')
    result, ids = {}, set()
    for row in rows:
        pattern = compile_pattern(row)
        pattern.validate_reporting(profile, time_scale)
        if pattern.code in result or pattern.id in ids:
            raise DefinitionError('duplicate pattern id/code')
        result[pattern.code] = pattern; ids.add(pattern.id)
    return result
