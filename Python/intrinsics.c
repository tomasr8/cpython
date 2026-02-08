
#define _PY_INTERPRETER

#include "Python.h"
#include "pycore_compile.h"       // _PyCompile_GetUnaryIntrinsicName
#include "pycore_function.h"      // _Py_set_function_type_params()
#include "pycore_genobject.h"     // _PyAsyncGenValueWrapperNew
#include "pycore_interpframe.h"   // _PyFrame_GetLocals()
#include "pycore_intrinsics.h"    // INTRINSIC_PRINT
#include "pycore_pyerrors.h"      // _PyErr_SetString()
#include "pycore_runtime.h"       // _Py_ID()
#include "pycore_typevarobject.h" // _Py_make_typevar()
#include "pycore_unicodeobject.h" // _PyUnicode_FromASCII()


/******** Unary functions ********/

static PyObject *
no_intrinsic1(PyThreadState* tstate, PyObject *unused)
{
    _PyErr_SetString(tstate, PyExc_SystemError, "invalid intrinsic function");
    return NULL;
}

static PyObject *
print_expr(PyThreadState* Py_UNUSED(ignored), PyObject *value)
{
    PyObject *hook = PySys_GetAttr(&_Py_ID(displayhook));
    if (hook == NULL) {
        return NULL;
    }
    PyObject *res = PyObject_CallOneArg(hook, value);
    Py_DECREF(hook);
    return res;
}

static int
import_all_from(PyThreadState *tstate, PyObject *locals, PyObject *v)
{
    PyObject *all, *dict, *name, *value;
    int skip_leading_underscores = 0;
    int pos, err;

    if (PyObject_GetOptionalAttr(v, &_Py_ID(__all__), &all) < 0) {
        return -1; /* Unexpected error */
    }
    if (all == NULL) {
        if (PyObject_GetOptionalAttr(v, &_Py_ID(__dict__), &dict) < 0) {
            return -1;
        }
        if (dict == NULL) {
            _PyErr_SetString(tstate, PyExc_ImportError,
                    "from-import-* object has no __dict__ and no __all__");
            return -1;
        }
        all = PyMapping_Keys(dict);
        Py_DECREF(dict);
        if (all == NULL)
            return -1;
        skip_leading_underscores = 1;
    }

    for (pos = 0, err = 0; ; pos++) {
        name = PySequence_GetItem(all, pos);
        if (name == NULL) {
            if (!_PyErr_ExceptionMatches(tstate, PyExc_IndexError)) {
                err = -1;
            }
            else {
                _PyErr_Clear(tstate);
            }
            break;
        }
        if (!PyUnicode_Check(name)) {
            PyObject *modname = PyObject_GetAttr(v, &_Py_ID(__name__));
            if (modname == NULL) {
                Py_DECREF(name);
                err = -1;
                break;
            }
            if (!PyUnicode_Check(modname)) {
                _PyErr_Format(tstate, PyExc_TypeError,
                              "module __name__ must be a string, not %.100s",
                              Py_TYPE(modname)->tp_name);
            }
            else {
                _PyErr_Format(tstate, PyExc_TypeError,
                              "%s in %U.%s must be str, not %.100s",
                              skip_leading_underscores ? "Key" : "Item",
                              modname,
                              skip_leading_underscores ? "__dict__" : "__all__",
                              Py_TYPE(name)->tp_name);
            }
            Py_DECREF(modname);
            Py_DECREF(name);
            err = -1;
            break;
        }
        if (skip_leading_underscores) {
            if (PyUnicode_READ_CHAR(name, 0) == '_') {
                Py_DECREF(name);
                continue;
            }
        }
        value = PyObject_GetAttr(v, name);
        if (value == NULL)
            err = -1;
        else if (PyDict_CheckExact(locals))
            err = PyDict_SetItem(locals, name, value);
        else
            err = PyObject_SetItem(locals, name, value);
        Py_DECREF(name);
        Py_XDECREF(value);
        if (err < 0)
            break;
    }
    Py_DECREF(all);
    return err;
}

static PyObject *
import_star(PyThreadState* tstate, PyObject *from)
{
    _PyInterpreterFrame *frame = tstate->current_frame;

    PyObject *locals = _PyFrame_GetLocals(frame);
    if (locals == NULL) {
        _PyErr_SetString(tstate, PyExc_SystemError,
                            "no locals found during 'import *'");
        return NULL;
    }
    int err = import_all_from(tstate, locals, from);
    Py_DECREF(locals);
    if (err < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
stopiteration_error(PyThreadState* tstate, PyObject *exc)
{
    _PyInterpreterFrame *frame = tstate->current_frame;
    assert(frame->owner == FRAME_OWNED_BY_GENERATOR);
    assert(PyExceptionInstance_Check(exc));
    const char *msg = NULL;
    if (PyErr_GivenExceptionMatches(exc, PyExc_StopIteration)) {
        msg = "generator raised StopIteration";
        if (_PyFrame_GetCode(frame)->co_flags & CO_ASYNC_GENERATOR) {
            msg = "async generator raised StopIteration";
        }
        else if (_PyFrame_GetCode(frame)->co_flags & CO_COROUTINE) {
            msg = "coroutine raised StopIteration";
        }
    }
    else if ((_PyFrame_GetCode(frame)->co_flags & CO_ASYNC_GENERATOR) &&
            PyErr_GivenExceptionMatches(exc, PyExc_StopAsyncIteration))
    {
        /* code in `gen` raised a StopAsyncIteration error:
        raise a RuntimeError.
        */
        msg = "async generator raised StopAsyncIteration";
    }
    if (msg != NULL) {
        PyObject *message = _PyUnicode_FromASCII(msg, strlen(msg));
        if (message == NULL) {
            return NULL;
        }
        PyObject *error = PyObject_CallOneArg(PyExc_RuntimeError, message);
        if (error == NULL) {
            Py_DECREF(message);
            return NULL;
        }
        assert(PyExceptionInstance_Check(error));
        PyException_SetCause(error, Py_NewRef(exc));
        // Steal exc reference, rather than Py_NewRef+Py_DECREF
        PyException_SetContext(error, Py_NewRef(exc));
        Py_DECREF(message);
        return error;
    }
    return Py_NewRef(exc);
}

static PyObject *
unary_pos(PyThreadState* unused, PyObject *value)
{
    return PyNumber_Positive(value);
}

static PyObject *
list_to_tuple(PyThreadState* unused, PyObject *v)
{
    assert(PyList_Check(v));
    return PyTuple_FromArray(((PyListObject *)v)->ob_item, Py_SIZE(v));
}

static PyObject *
make_typevar(PyThreadState* Py_UNUSED(ignored), PyObject *v)
{
    assert(PyUnicode_Check(v));
    return _Py_make_typevar(v, NULL, NULL);
}


#define INTRINSIC_FUNC_ENTRY(N, F) \
    [N] = {F, #N},

const intrinsic_func1_info
_PyIntrinsics_UnaryFunctions[] = {
    INTRINSIC_FUNC_ENTRY(INTRINSIC_1_INVALID, no_intrinsic1)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_PRINT, print_expr)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_IMPORT_STAR, import_star)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_STOPITERATION_ERROR, stopiteration_error)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_ASYNC_GEN_WRAP, _PyAsyncGenValueWrapperNew)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_UNARY_POSITIVE, unary_pos)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_LIST_TO_TUPLE, list_to_tuple)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_TYPEVAR, make_typevar)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_PARAMSPEC, _Py_make_paramspec)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_TYPEVARTUPLE, _Py_make_typevartuple)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_SUBSCRIPT_GENERIC, _Py_subscript_generic)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_TYPEALIAS, _Py_make_typealias)
};


/******** Binary functions ********/

static PyObject *
no_intrinsic2(PyThreadState* tstate, PyObject *unused1, PyObject *unused2)
{
    _PyErr_SetString(tstate, PyExc_SystemError, "invalid intrinsic function");
    return NULL;
}

static PyObject *
prep_reraise_star(PyThreadState* unused, PyObject *orig, PyObject *excs)
{
    assert(PyList_Check(excs));
    return _PyExc_PrepReraiseStar(orig, excs);
}

static PyObject *
make_typevar_with_bound(PyThreadState* Py_UNUSED(ignored), PyObject *name,
                        PyObject *evaluate_bound)
{
    assert(PyUnicode_Check(name));
    return _Py_make_typevar(name, evaluate_bound, NULL);
}

static PyObject *
make_typevar_with_constraints(PyThreadState* Py_UNUSED(ignored), PyObject *name,
                              PyObject *evaluate_constraints)
{
    assert(PyUnicode_Check(name));
    return _Py_make_typevar(name, NULL, evaluate_constraints);
}

static PyObject *
destructure_mapping(PyThreadState* tstate, PyObject *obj, PyObject *keys_tuple)
{
    assert(PyTuple_Check(keys_tuple));
    Py_ssize_t n = PyTuple_GET_SIZE(keys_tuple);
    PyObject *result = PyTuple_New(n);
    if (result == NULL) {
        return NULL;
    }
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *key = PyTuple_GET_ITEM(keys_tuple, i);
        assert(PyUnicode_Check(key));
        /* Try __getitem__ first */
        PyObject *value = PyObject_GetItem(obj, key);
        if (value == NULL) {
            if (_PyErr_ExceptionMatches(tstate, PyExc_KeyError) ||
                _PyErr_ExceptionMatches(tstate, PyExc_TypeError)) {
                _PyErr_Clear(tstate);
                /* Fall back to getattr */
                value = PyObject_GetAttr(obj, key);
                if (value == NULL) {
                    Py_DECREF(result);
                    return NULL;
                }
            }
            else {
                Py_DECREF(result);
                return NULL;
            }
        }
        PyTuple_SET_ITEM(result, i, value);
    }
    return result;
}

static PyObject *
destructure_mapping_rest(PyThreadState* tstate, PyObject *obj, PyObject *keys_tuple)
{
    assert(PyTuple_Check(keys_tuple));
    Py_ssize_t n = PyTuple_GET_SIZE(keys_tuple);

    /* First, extract the named values (same logic as destructure_mapping) */
    PyObject **values = PyMem_Malloc((n + 1) * sizeof(PyObject *));
    if (values == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *key = PyTuple_GET_ITEM(keys_tuple, i);
        assert(PyUnicode_Check(key));
        PyObject *value = PyObject_GetItem(obj, key);
        if (value == NULL) {
            if (_PyErr_ExceptionMatches(tstate, PyExc_KeyError) ||
                _PyErr_ExceptionMatches(tstate, PyExc_TypeError)) {
                _PyErr_Clear(tstate);
                value = PyObject_GetAttr(obj, key);
                if (value == NULL) {
                    goto error;
                }
            }
            else {
                goto error;
            }
        }
        values[i] = value;
    }

    /* Build the rest dict */
    PyObject *rest_dict = NULL;

    /* Try dict-like: use .items() */
    PyObject *items_method = NULL;
    if (PyObject_GetOptionalAttr(obj, &_Py_ID(items), &items_method) < 0) {
        goto error;
    }
    if (items_method != NULL) {
        PyObject *items = PyObject_CallNoArgs(items_method);
        Py_DECREF(items_method);
        if (items == NULL) {
            goto error;
        }
        PyObject *iter = PyObject_GetIter(items);
        Py_DECREF(items);
        if (iter == NULL) {
            goto error;
        }
        rest_dict = PyDict_New();
        if (rest_dict == NULL) {
            Py_DECREF(iter);
            goto error;
        }
        PyObject *item;
        while ((item = PyIter_Next(iter)) != NULL) {
            PyObject *k = PyTuple_GET_ITEM(item, 0);
            PyObject *v = PyTuple_GET_ITEM(item, 1);
            /* Check if k is in keys_tuple */
            int found = 0;
            for (Py_ssize_t i = 0; i < n; i++) {
                int eq = PyObject_RichCompareBool(k, PyTuple_GET_ITEM(keys_tuple, i), Py_EQ);
                if (eq < 0) {
                    Py_DECREF(item);
                    Py_DECREF(iter);
                    Py_DECREF(rest_dict);
                    goto error;
                }
                if (eq) {
                    found = 1;
                    break;
                }
            }
            if (!found) {
                if (PyDict_SetItem(rest_dict, k, v) < 0) {
                    Py_DECREF(item);
                    Py_DECREF(iter);
                    Py_DECREF(rest_dict);
                    goto error;
                }
            }
            Py_DECREF(item);
        }
        Py_DECREF(iter);
        if (PyErr_Occurred()) {
            Py_DECREF(rest_dict);
            goto error;
        }
    }
    else {
        /* Object fallback: use vars(obj) */
        PyObject *vars_dict = PyObject_GenericGetDict(obj, NULL);
        if (vars_dict == NULL) {
            /* Try __dict__ attribute */
            _PyErr_Clear(tstate);
            vars_dict = PyObject_GetAttr(obj, &_Py_ID(__dict__));
            if (vars_dict == NULL) {
                goto error;
            }
        }
        rest_dict = PyDict_New();
        if (rest_dict == NULL) {
            Py_DECREF(vars_dict);
            goto error;
        }
        PyObject *dk, *dv;
        Py_ssize_t pos = 0;
        while (PyDict_Next(vars_dict, &pos, &dk, &dv)) {
            /* Skip private attributes */
            if (PyUnicode_Check(dk) && PyUnicode_READ_CHAR(dk, 0) == '_') {
                continue;
            }
            /* Skip keys in keys_tuple */
            int found = 0;
            for (Py_ssize_t i = 0; i < n; i++) {
                int eq = PyObject_RichCompareBool(dk, PyTuple_GET_ITEM(keys_tuple, i), Py_EQ);
                if (eq < 0) {
                    Py_DECREF(vars_dict);
                    Py_DECREF(rest_dict);
                    goto error;
                }
                if (eq) {
                    found = 1;
                    break;
                }
            }
            if (!found) {
                if (PyDict_SetItem(rest_dict, dk, dv) < 0) {
                    Py_DECREF(vars_dict);
                    Py_DECREF(rest_dict);
                    goto error;
                }
            }
        }
        Py_DECREF(vars_dict);
    }

    /* Build result tuple: (val1, val2, ..., rest_dict) */
    PyObject *result = PyTuple_New(n + 1);
    if (result == NULL) {
        Py_DECREF(rest_dict);
        goto error;
    }
    for (Py_ssize_t i = 0; i < n; i++) {
        PyTuple_SET_ITEM(result, i, values[i]);  /* steals ref */
    }
    PyTuple_SET_ITEM(result, n, rest_dict);  /* steals ref */
    PyMem_Free(values);
    return result;

error:
    for (Py_ssize_t i = 0; i < n; i++) {
        Py_XDECREF(values[i]);
    }
    PyMem_Free(values);
    return NULL;
}

const intrinsic_func2_info
_PyIntrinsics_BinaryFunctions[] = {
    INTRINSIC_FUNC_ENTRY(INTRINSIC_2_INVALID, no_intrinsic2)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_PREP_RERAISE_STAR, prep_reraise_star)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_TYPEVAR_WITH_BOUND, make_typevar_with_bound)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_TYPEVAR_WITH_CONSTRAINTS, make_typevar_with_constraints)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_SET_FUNCTION_TYPE_PARAMS, _Py_set_function_type_params)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_SET_TYPEPARAM_DEFAULT, _Py_set_typeparam_default)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_DESTRUCTURE, destructure_mapping)
    INTRINSIC_FUNC_ENTRY(INTRINSIC_DESTRUCTURE_REST, destructure_mapping_rest)
};

#undef INTRINSIC_FUNC_ENTRY

PyObject*
_PyCompile_GetUnaryIntrinsicName(int index)
{
    if (index < 0 || index > MAX_INTRINSIC_1) {
        return NULL;
    }
    return PyUnicode_FromString(_PyIntrinsics_UnaryFunctions[index].name);
}

PyObject*
_PyCompile_GetBinaryIntrinsicName(int index)
{
    if (index < 0 || index > MAX_INTRINSIC_2) {
        return NULL;
    }
    return PyUnicode_FromString(_PyIntrinsics_BinaryFunctions[index].name);
}
