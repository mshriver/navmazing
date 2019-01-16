import logging

import pytest
from wait_for import TimedOutError

from navmazing import (
    Navigate,
    NavigateStep,
    NavigateToSibling,
    NavigationTriesExceeded,
    NavigationDestinationNotFound,
    NavigateToAttribute,
    NavigateToObject,
)


state = []
arg_store = []

logger = logging.getLogger('navmazing_null')
for handler in logger.handlers:
    logger.removeHandler(handler)

file_formatter = logging.Formatter('%(asctime)-15s [%(levelname).1s] %(message)s')
file_handler = logging.FileHandler('navmazing.log')
file_handler.setFormatter(file_formatter)

logger.addHandler(file_handler)
logger.setLevel(10)

navigate = Navigate(logger)


@pytest.fixture(scope='function')
def clear_state():
    del state[:]


class ObjectA(object):

    def __init__(self, name):
        self.name = name
        self.margs = None
        self.kwargs = None


class ObjectB(object):

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent


class ObjectC(object):

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent


@navigate.register(ObjectB)
class StepTwoAgain(NavigateStep):
    prerequisite = NavigateToAttribute("parent", "StepOne")

    def step(self):
        state.append(self._name)


@navigate.register(ObjectB, "StepTwo")
class StepTwoToo(NavigateStep):

    def prerequisite(self):
        self.navigate_obj.navigate(self.obj.parent, "StepOne")

    def step(self):
        state.append(self._name)


@navigate.register(ObjectA, "BadStep")
class BadStep(NavigateStep):
    prerequisite = NavigateToSibling("StepZero")

    def step(self):
        1 / 0


@navigate.register(ObjectA, "BadStepReturn")
class BadStepReturn(NavigateStep):
    prerequisite = NavigateToSibling("StepZero")

    def am_i_here(self):
        1 / 0


@navigate.register(ObjectA, "StepOne")
class StepOne(NavigateStep):
    prerequisite = NavigateToSibling("StepZero")

    def step(self):
        state.append(self._name)


@navigate.register(ObjectA, "StepZero")
class StepZero(NavigateStep):

    def am_i_here(self):
        return bool(state)

    def step(self):
        state.append(self._name)


@navigate.register(ObjectB, "NeedA")
class NeedA(NavigateStep):

    prerequisite = NavigateToObject(ObjectA, "StepOne")

    def step(self):
        state.append(self._name)


@navigate.register(ObjectA, "StepZeroArgs")
class StepZeroArgs(NavigateStep):

    def am_i_here(self, *args, **kwargs):
        return bool(state)

    def step(self, *args, **kwargs):
        self.obj.margs = list(args)
        self.obj.kwargs = kwargs


@navigate.register(ObjectA, "IncludeResetter")
class IncludeResetter(NavigateStep):
    prerequisite = NavigateToSibling('StepZero')

    def step(self):
        state.append(self._name)

    def resetter(self):
        state.append('ResetterUsed')


@navigate.register(ObjectA, "NeverHere")
class NeverHere(NavigateStep):
    prerequisite = NavigateToSibling('StepZero')

    def am_i_here(self, *args, **kwargs):
        return False  # I was never here!

    def step(self):
        state.append(self._name)


def test_navigation_to_instance(clear_state):
    a = ObjectA("ObjectA")
    b = ObjectB("ObjectB", a)
    navigate.navigate(b, "StepTwo")
    assert state == ["StepZero", "StepOne", "StepTwo"]


def test_navigation_to_class(clear_state):
    a = ObjectA
    b = ObjectB(ObjectA, a)
    navigate.navigate(b, "StepTwo")
    assert state == ["StepZero", "StepOne", "StepTwo"]


def test_navigation_to_non_named_step(clear_state):
    a = ObjectA
    b = ObjectB(ObjectA, a)
    navigate.navigate(b, "StepTwoAgain")
    assert state == ["StepZero", "StepOne", "StepTwoAgain"]


def test_bad_step_exception(clear_state):
    a = ObjectA
    b = ObjectB(ObjectA, a)
    with pytest.raises(NavigationDestinationNotFound):
        navigate.navigate(b, "Weird")


def test_bad_step_multi(clear_state):
    a = ObjectA
    b = ObjectB(ObjectA, a)
    with pytest.raises(NavigationDestinationNotFound):
        try:
            navigate.navigate(b, "Whoop")
        except NavigationDestinationNotFound as e:
            assert str(e) == (
                "Couldn't find the destination [{}] with the given class [{}] "
                "the following were available [{}]"
            ).format("Whoop", "ObjectB", ", ".join(sorted(["NeedA", "StepTwo, StepTwoAgain"])))
            raise


def test_bad_object_exception():
    c = ObjectC("ObjectC")
    with pytest.raises(NavigationDestinationNotFound):
        try:
            navigate.navigate(c, "NotHere")
        except NavigationDestinationNotFound as e:
            assert str(e) == (
                "Couldn't find the destination [{}] with the given class [{}] "
                "the following were available [{}]"
            ).format("NotHere", "ObjectC", "")
            raise


def test_bad_step(clear_state):
    a = ObjectA("ObjectA")
    with pytest.raises(NavigationTriesExceeded):
        try:
            navigate.navigate(a, "BadStep")
        except NavigationTriesExceeded as e:
            assert str(e) == "Navigation failed to reach [{}] in the specificed tries".format(
                "BadStep"
            )
            raise


def test_no_nav():
    a = ObjectA
    b = ObjectB(ObjectA, a)
    navigate.navigate(b, "StepTwo")
    assert state == ["StepZero", "StepOne", "StepTwo"]


def test_bad_am_i_here(clear_state):
    a = ObjectA
    navigate.navigate(a, "BadStepReturn")


def test_list_destinations():
    expected = {
        "StepZero",
        "BadStepReturn",
        "BadStep",
        "StepOne",
        "StepZeroArgs",
        "IncludeResetter",
        "NeverHere"
    }
    assert expected == navigate.list_destinations(ObjectA)


def test_navigate_to_object(clear_state):
    b = ObjectB("a", "a")
    navigate.navigate(b, "NeedA")
    assert state == ["StepZero", "StepOne", "NeedA"]


def test_navigate_wth_args(clear_state):
    a = ObjectA
    args = [1, 2, 3]
    kwargs = {"a": "A", "b": "B"}
    navigate.navigate(a, "StepZeroArgs", *args, **kwargs)
    assert a.margs == args


def test_navigate_resetter_control(clear_state):
    """Test control of the resetter method calling via use_resetter kwarg"""
    a = ObjectA
    navigate.navigate(a, 'IncludeResetter')
    assert state == ["StepZero", 'IncludeResetter', 'ResetterUsed']

    # clear state again
    del state[:]
    navigate.navigate(a, 'IncludeResetter', use_resetter=False)
    assert state == ["StepZero", 'IncludeResetter']


def test_navigate_wait_control(clear_state):
    """Test control of waiting for am_i_here after navigation via wait_for_view kwarg"""
    a = ObjectA
    navigate.navigate(a, "NeverHere")
    assert state == ["StepZero", "NeverHere"]

    del state[:]
    with pytest.raises(TimedOutError):
        navigate.navigate(a, "NeverHere", wait_for_view=2)


def test_get_name():
    a = ObjectA
    nav = navigate.get_class(a, "BadStep")
    assert nav == BadStep
