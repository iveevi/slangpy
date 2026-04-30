// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

// All widget render() methods are defined inline in widgets.h so the vtables
// emit per-TU and aren't hidden by -fvisibility=hidden when the binding
// layer (slangpy_ext) instantiates them.
