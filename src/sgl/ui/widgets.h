// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "sgl/core/object.h"
#include "sgl/device/fwd.h"
#include "sgl/math/vector_types.h"

#include <imgui.h>
#include <imgui_internal.h>
#include <implot.h>

#include <algorithm>
#include <map>
#include <string_view>
#include <string>
#include <functional>
#include <vector>

namespace sgl::ui {

class Widget;

/// Base class for Python UI widgets.
/// Widgets own their children.
class SGL_API Widget : public Object {
    SGL_OBJECT(Widget)
public:
    Widget(Widget* parent)
        : m_parent(parent)
    {
        if (m_parent)
            m_parent->m_children.push_back(ref<Widget>(this));
    }

    virtual ~Widget() { }

    Widget* parent() { return m_parent; }
    const Widget* parent() const { return m_parent; }
    void set_parent(Widget* parent) { m_parent = parent; }

    const std::vector<ref<Widget>>& children() const { return m_children; }
    size_t child_count() const { return m_children.size(); }
    void clear_children() { m_children.clear(); }

    int child_index(const Widget* child) const
    {
        auto it = std::find(m_children.begin(), m_children.end(), child);
        return it != m_children.end() ? int(std::distance(m_children.begin(), it)) : -1;
    }

    ref<Widget> child_at(size_t index) const
    {
        SGL_CHECK(index < m_children.size(), "index out of bounds");
        return m_children[index];
    }

    void add_child(ref<Widget> child)
    {
        SGL_CHECK_NOT_NULL(child);
        m_children.push_back(child);
        child->set_parent(this);
    }

    void add_child_at(ref<Widget> child, size_t index)
    {
        SGL_CHECK_NOT_NULL(child);
        SGL_CHECK(index == 0 || index < m_children.size(), "index out of bounds");
        m_children.insert(m_children.begin() + index, child);
        child->set_parent(this);
    }

    void remove_child(ref<Widget> child)
    {
        auto it = std::find(m_children.begin(), m_children.end(), child);
        SGL_CHECK(it != m_children.end(), "child widget not found");
        m_children.erase(it);
        child->set_parent(nullptr);
    }

    void remove_child_at(size_t index)
    {
        SGL_CHECK(index < m_children.size(), "index out of bounds");
        auto child = m_children[index];
        m_children.erase(m_children.begin() + index);
        child->set_parent(nullptr);
    }

    void remove_all_children()
    {
        for (auto& child : m_children)
            child->set_parent(nullptr);
        m_children.clear();
    }

    bool visible() const { return m_visible; }
    void set_visible(bool visible) { m_visible = visible; }

    bool enabled() const { return m_enabled; }
    void set_enabled(bool enabled) { m_enabled = enabled; }

    virtual void render();

protected:
    Widget* m_parent;
    std::vector<ref<Widget>> m_children;
    bool m_visible{true};
    bool m_enabled{true};
};

/// This is the main widget that represents the screen.
/// It is intended to be used as the parent for \c Window widgets.
class SGL_API Screen : public Widget {
    SGL_OBJECT(Screen)
public:
    Screen()
        : Widget(nullptr)
    {
    }

    virtual void render() override;
};

/// Scoped push/pop of ImGui ID.
class ScopedID {
public:
    ScopedID(void* id) { ImGui::PushID(id); }
    ~ScopedID() { ImGui::PopID(); }
};

/// Scoped begin/end for disabling ImGUI widgets.
class ScopedDisable {
public:
    ScopedDisable(bool disabled)
        : m_disabled(disabled)
    {
        if (disabled)
            ImGui::BeginDisabled();
    }
    ~ScopedDisable()
    {
        if (m_disabled)
            ImGui::EndDisabled();
    }

private:
    bool m_disabled;
};

class SGL_API Window : public Widget {
    SGL_OBJECT(Window)
public:
    Window(
        Widget* parent,
        std::string_view title = "",
        float2 position = float2(10.f, 10.f),
        float2 size = float2(400.f, 400.f),
        bool show_title_bar = true,
        bool overlay = false
    )
        : Widget(parent)
        , m_title(title)
        , m_position(position)
        , m_size(size)
        , m_show_title_bar(show_title_bar)
        , m_overlay(overlay)
    {
    }

    const std::string& title() const { return m_title; }
    void set_title(std::string_view title) { m_title = title; }

    bool show_title_bar() const { return m_show_title_bar; }
    void set_show_title_bar(bool show) { m_show_title_bar = show; }

    /// Render as a chrome-less overlay: transparent background, no title
    /// bar / resize / move / docking, auto-sized to its content. Combine
    /// with set_position() to pin a floating toolbar over another panel
    /// (e.g. on top of a viewport image). All public ImGui window flags.
    bool overlay() const { return m_overlay; }
    void set_overlay(bool overlay) { m_overlay = overlay; }

    float2 position() const { return m_position; }
    void set_position(const float2& position)
    {
        m_position = position;
        m_set_position = true;
    }

    float2 size() const { return m_size; }
    void set_size(const float2& size)
    {
        m_size = size;
        m_set_size = true;
    }

    /// Inner padding (ImGuiStyleVar_WindowPadding). A negative component
    /// uses the global style default; set to (0,0) to let content (e.g. an
    /// Image) fill the window edge-to-edge.
    float2 padding() const { return m_padding; }
    void set_padding(const float2& padding) { m_padding = padding; }

    /// Size of the content region available inside the window, captured on
    /// the last render. Useful for sizing a render target to the window.
    float2 content_size() const { return m_content_size; }

    void show() { set_visible(true); }
    void close() { set_visible(false); }

    /// Dock this window onto the given dock node on its next render.
    /// Pass \c 0 to detach (let the user dock manually).
    uint32_t dock_id() const { return m_dock_id; }
    void set_dock_id(uint32_t dock_id)
    {
        m_dock_id = dock_id;
        m_set_dock_id = true;
    }

    virtual void render() override;

private:
    std::string m_title;
    float2 m_position;
    float2 m_size;
    bool m_set_position{false};
    bool m_set_size{false};
    uint32_t m_dock_id{0};
    bool m_set_dock_id{false};
    bool m_show_title_bar{true};
    bool m_overlay{false};
    float2 m_padding{-1.f, -1.f};
    float2 m_content_size{0.f, 0.f};
};

class SGL_API Group : public Widget {
    SGL_OBJECT(Group)
public:
    Group(Widget* parent, std::string_view label = "")
        : Widget(parent)
        , m_label(label)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    virtual void render() override;

private:
    std::string m_label;
};

/// Collapsible tree node. Unlike Group, the open/close state is
/// programmatically controllable via the `open` property and reflects
/// user interaction back after each frame.
class SGL_API TreeNode : public Widget {
    SGL_OBJECT(TreeNode)
public:
    TreeNode(Widget* parent, std::string_view label = "", bool open = false)
        : Widget(parent)
        , m_label(label)
        , m_open(open)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    bool open() const { return m_open; }
    void set_open(bool open)
    {
        m_open = open;
        m_set_open = true;
    }

    virtual void render() override;

private:
    std::string m_label;
    bool m_open{false};
    bool m_set_open{false};
};

class SGL_API Text : public Widget {
    SGL_OBJECT(Text)
public:
    Text(Widget* parent, std::string_view text = "")
        : Widget(parent)
        , m_text(text)
    {
    }

    const std::string& text() const { return m_text; }
    void set_text(std::string_view text) { m_text = text; }

    virtual void render() override;

private:
    std::string m_text;
};

class SGL_API Separator : public Widget {
    SGL_OBJECT(Separator)
public:
    Separator(Widget* parent, std::string_view label = "")
        : Widget(parent)
        , m_label(label)
    {
    }
    const std::string& label() const { return m_label; }
    void set_label(std::string_view v) { m_label = v; }
    virtual void render() override;

private:
    std::string m_label;
};

class SGL_API ProgressBar : public Widget {
    SGL_OBJECT(ProgressBar)
public:
    ProgressBar(Widget* parent, float fraction = 0.f)
        : Widget(parent)
        , m_fraction(fraction)
    {
    }

    float fraction() const { return m_fraction; }
    void set_fraction(float fraction) { m_fraction = fraction; }

    virtual void render() override;

private:
    float m_fraction;
};

class SGL_API Button : public Widget {
    SGL_OBJECT(Button)
public:
    using Callback = std::function<void()>;

    Button(
        Widget* parent,
        std::string_view label = "",
        Callback callback = {},
        bool active = false,
        bool border = false
    )
        : Widget(parent)
        , m_label(label)
        , m_callback(callback)
        , m_active(active)
        , m_border(border)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    Callback callback() const { return m_callback; }
    void set_callback(Callback callback) { m_callback = callback; }

    /// When true the button is drawn filled with the theme's accent
    /// (ImGuiCol_HeaderActive) to show a selected/toggled state. Use for
    /// radio-style button groups. Purely a style push around ImGui::Button.
    bool active() const { return m_active; }
    void set_active(bool active) { m_active = active; }

    /// When true the button is drawn with a 1px frame border (ImGuiCol_Border)
    /// even if the global FrameBorderSize is 0. Style push around ImGui::Button.
    bool border() const { return m_border; }
    void set_border(bool border) { m_border = border; }

    void notify()
    {
        if (m_callback)
            m_callback();
    }

    virtual void render() override;

private:
    std::string m_label;
    Callback m_callback;
    bool m_active{false};
    bool m_border{false};
};

/// Places the next sibling widget on the same line as the previous one
/// (ImGui::SameLine). Use between widgets to lay them out horizontally.
class SGL_API SameLine : public Widget {
    SGL_OBJECT(SameLine)
public:
    SameLine(Widget* parent, float offset_x = 0.f, float spacing = -1.f)
        : Widget(parent)
        , m_offset_x(offset_x)
        , m_spacing(spacing)
    {
    }

    float offset_x() const { return m_offset_x; }
    void set_offset_x(float v) { m_offset_x = v; }

    float spacing() const { return m_spacing; }
    void set_spacing(float v) { m_spacing = v; }

    virtual void render() override;

private:
    float m_offset_x;
    float m_spacing;
};

/// Moves the draw cursor to a position relative to the window's content
/// region top-left, so following sibling widgets can be placed at an
/// explicit spot -- e.g. overlaid on top of a preceding Image in the same
/// window. (Relative to the content origin, not the window origin, so it
/// stays clear of the title/tab bar.)
class SGL_API CursorPos : public Widget {
    SGL_OBJECT(CursorPos)
public:
    CursorPos(Widget* parent, float2 pos = float2(0.f, 0.f))
        : Widget(parent)
        , m_pos(pos)
    {
    }

    float2 pos() const { return m_pos; }
    void set_pos(const float2& pos) { m_pos = pos; }

    virtual void render() override;

private:
    float2 m_pos;
};

template<typename T>
class ValueProperty : public Widget {
public:
    using value_type = T;
    using Callback = std::function<void(const value_type&)>;

    ValueProperty(Widget* parent, std::string_view label, value_type value, Callback callback)
        : Widget(parent)
        , m_label(label)
        , m_value(value)
        , m_callback(callback)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    const value_type& value() const { return m_value; }
    void set_value(const value_type& value) { m_value = value; }

    Callback callback() const { return m_callback; }
    void set_callback(Callback callback) { m_callback = callback; }

    void notify()
    {
        if (m_callback)
            m_callback(m_value);
    }

protected:
    std::string m_label;
    value_type m_value;
    Callback m_callback;
};

class SGL_API CheckBox : public ValueProperty<bool> {
    SGL_OBJECT(CheckBox)
public:
    using Base = ValueProperty<bool>;

    CheckBox(Widget* parent, std::string_view label = "", bool value = false, Callback callback = {})
        : Base(parent, label, value, callback)
    {
    }

    virtual void render() override;
};

class SGL_API ComboBox : public ValueProperty<int> {
    SGL_OBJECT(ComboBox)
public:
    using Base = ValueProperty<int>;

    ComboBox(
        Widget* parent,
        std::string_view label = "",
        int value = 0,
        Callback callback = {},
        std::vector<std::string> items = {}
    )
        : Base(parent, label, value, callback)
        , m_items(items)
    {
    }

    const std::vector<std::string>& items() const { return m_items; }
    void set_items(const std::vector<std::string>& items) { m_items = items; }

    virtual void render() override;

private:
    std::vector<std::string> m_items;
};

class SGL_API ListBox : public ValueProperty<int> {
    SGL_OBJECT(ListBox)
public:
    using Base = ValueProperty<int>;

    ListBox(
        Widget* parent,
        std::string_view label = "",
        int value = 0,
        Callback callback = {},
        std::vector<std::string> items = {},
        int height_in_items = -1
    )
        : Base(parent, label, value, callback)
        , m_items(items)
        , m_height_in_items(height_in_items)
    {
    }

    const std::vector<std::string>& items() const { return m_items; }
    void set_items(const std::vector<std::string>& items) { m_items = items; }

    int height_in_items() const { return m_height_in_items; }
    void set_height_in_items(int height_in_items) { m_height_in_items = height_in_items; }

    virtual void render() override;

private:
    std::vector<std::string> m_items;
    int m_height_in_items;
};

enum class SliderFlags {
    none = ImGuiSliderFlags_None,
    always_clamp = ImGuiSliderFlags_AlwaysClamp,
    logarithmic = ImGuiSliderFlags_Logarithmic,
    no_round_to_format = ImGuiSliderFlags_NoRoundToFormat,
    no_input = ImGuiSliderFlags_NoInput,
};

SGL_ENUM_CLASS_OPERATORS(SliderFlags);

template<typename T>
struct DataTypeTraits { };

// clang-format off
template<> struct DataTypeTraits<float> { static constexpr ImGuiDataType data_type{ImGuiDataType_Float}; static constexpr const char* default_format = "%.3f"; };
template<> struct DataTypeTraits<int> { static constexpr ImGuiDataType data_type{ImGuiDataType_S32}; static constexpr const char* default_format = "%d"; };
// clang-format on


template<typename T>
struct VectorTraits { };

// clang-format off
template<> struct VectorTraits<float> { using scalar_type = float; static constexpr int N = 1; };
template<> struct VectorTraits<float2> { using scalar_type = float; static constexpr int N = 2; };
template<> struct VectorTraits<float3> { using scalar_type = float; static constexpr int N = 3; };
template<> struct VectorTraits<float4> { using scalar_type = float; static constexpr int N = 4; };
template<> struct VectorTraits<int> { using scalar_type = int; static constexpr int N = 1; };
template<> struct VectorTraits<int2> { using scalar_type = int; static constexpr int N = 2; };
template<> struct VectorTraits<int3> { using scalar_type = int; static constexpr int N = 3; };
template<> struct VectorTraits<int4> { using scalar_type = int; static constexpr int N = 4; };
// clang-format on

template<typename T>
class Drag : public ValueProperty<T> {
    SGL_OBJECT(Drag)
public:
    using Base = ValueProperty<T>;
    using typename Base::value_type;
    using typename Base::Callback;

    using Widget::m_enabled;
    using Widget::m_visible;
    using Base::m_label;
    using Base::m_value;
    using Base::notify;

    using scalar_type = typename VectorTraits<T>::scalar_type;
    static constexpr int N = VectorTraits<T>::N;
    static constexpr const char* default_format = DataTypeTraits<scalar_type>::default_format;

    Drag(
        Widget* parent,
        std::string_view label = "",
        value_type value = value_type(0),
        Callback callback = {},
        float speed = 1.f,
        scalar_type min = scalar_type(0),
        scalar_type max = scalar_type(0),
        std::string_view format = default_format,
        SliderFlags flags = SliderFlags::none
    )
        : Base(parent, label, value, callback)
        , m_speed(speed)
        , m_min(min)
        , m_max(max)
        , m_format(format)
        , m_flags(flags)
    {
    }

    scalar_type speed() const { return static_cast<scalar_type>(m_speed); }
    void set_speed(scalar_type speed) { m_speed = static_cast<float>(speed); }

    scalar_type min() const { return m_min; }
    void set_min(scalar_type min) { m_min = min; }

    scalar_type max() const { return m_max; }
    void set_max(scalar_type max) { m_max = max; }

    const std::string& format() const { return m_format; }
    void set_format(std::string_view format) { m_format = format; }

    SliderFlags flags() const { return m_flags; }
    void set_flags(SliderFlags flags) { m_flags = flags; }

    virtual void render() override
    {
        if (!m_visible)
            return;

        ScopedID id(this);
        ScopedDisable disable(!m_enabled);
        bool changed = ImGui::DragScalarN(
            m_label.c_str(),
            DataTypeTraits<scalar_type>::data_type,
            &m_value,
            N,
            m_speed,
            &m_min,
            &m_max,
            m_format.c_str(),
            ImGuiSliderFlags(m_flags)
        );
        if (changed)
            notify();
    }

private:
    float m_speed;
    scalar_type m_min;
    scalar_type m_max;
    std::string m_format;
    SliderFlags m_flags;
};

using DragFloat = Drag<float>;
using DragFloat2 = Drag<float2>;
using DragFloat3 = Drag<float3>;
using DragFloat4 = Drag<float4>;
using DragInt = Drag<int>;
using DragInt2 = Drag<int2>;
using DragInt3 = Drag<int3>;
using DragInt4 = Drag<int4>;

template<typename T>
class Slider : public ValueProperty<T> {
    SGL_OBJECT(Slider)
public:
    using Base = ValueProperty<T>;
    using typename Base::value_type;
    using typename Base::Callback;

    using Widget::m_enabled;
    using Widget::m_visible;
    using Base::m_label;
    using Base::m_value;
    using Base::notify;

    using scalar_type = typename VectorTraits<T>::scalar_type;
    static constexpr int N = VectorTraits<T>::N;
    static constexpr const char* default_format = DataTypeTraits<scalar_type>::default_format;

    Slider(
        Widget* parent,
        std::string_view label = "",
        value_type value = value_type(0),
        Callback callback = {},
        scalar_type min = scalar_type(0),
        scalar_type max = scalar_type(0),
        std::string_view format = default_format,
        SliderFlags flags = SliderFlags::none
    )
        : Base(parent, label, value, callback)
        , m_min(min)
        , m_max(max)
        , m_format(format)
        , m_flags(flags)
    {
    }

    scalar_type min() const { return m_min; }
    void set_min(scalar_type min) { m_min = min; }

    scalar_type max() const { return m_max; }
    void set_max(scalar_type max) { m_max = max; }

    const std::string& format() const { return m_format; }
    void set_format(std::string_view format) { m_format = format; }

    SliderFlags flags() const { return m_flags; }
    void set_flags(SliderFlags flags) { m_flags = flags; }

    virtual void render() override
    {
        if (!m_visible)
            return;

        ScopedID id(this);
        ScopedDisable disable(!m_enabled);
        bool changed = ImGui::SliderScalarN(
            m_label.c_str(),
            DataTypeTraits<scalar_type>::data_type,
            &m_value,
            N,
            &m_min,
            &m_max,
            m_format.c_str(),
            ImGuiSliderFlags(m_flags)
        );
        if (changed)
            notify();
    }

private:
    scalar_type m_min;
    scalar_type m_max;
    std::string m_format;
    SliderFlags m_flags;
};

using SliderFloat = Slider<float>;
using SliderFloat2 = Slider<float2>;
using SliderFloat3 = Slider<float3>;
using SliderFloat4 = Slider<float4>;
using SliderInt = Slider<int>;
using SliderInt2 = Slider<int2>;
using SliderInt3 = Slider<int3>;
using SliderInt4 = Slider<int4>;

enum class InputTextFlags {
    none = ImGuiInputTextFlags_None,
    chars_decimal = ImGuiInputTextFlags_CharsDecimal,
    chars_hexadecimal = ImGuiInputTextFlags_CharsHexadecimal,
    chars_uppercase = ImGuiInputTextFlags_CharsUppercase,
    chars_no_blank = ImGuiInputTextFlags_CharsNoBlank,
    auto_select_all = ImGuiInputTextFlags_AutoSelectAll,
    enter_returns_true = ImGuiInputTextFlags_EnterReturnsTrue,
    callback_completion = ImGuiInputTextFlags_CallbackCompletion,
    callback_history = ImGuiInputTextFlags_CallbackHistory,
    callback_always = ImGuiInputTextFlags_CallbackAlways,
    callback_char_filter = ImGuiInputTextFlags_CallbackCharFilter,
    allow_tab_input = ImGuiInputTextFlags_AllowTabInput,
    ctrl_enter_for_new_line = ImGuiInputTextFlags_CtrlEnterForNewLine,
    no_horizontal_scroll = ImGuiInputTextFlags_NoHorizontalScroll,
    always_overwrite = ImGuiInputTextFlags_AlwaysOverwrite,
    read_only = ImGuiInputTextFlags_ReadOnly,
    password = ImGuiInputTextFlags_Password,
    no_undo_redo = ImGuiInputTextFlags_NoUndoRedo,
    chars_scientific = ImGuiInputTextFlags_CharsScientific,
    escape_clears_all = ImGuiInputTextFlags_EscapeClearsAll,
};

SGL_ENUM_CLASS_OPERATORS(InputTextFlags);

template<typename T>
class Input : public ValueProperty<T> {
    SGL_OBJECT(Input)
public:
    using Base = ValueProperty<T>;
    using typename Base::value_type;
    using typename Base::Callback;

    using Widget::m_enabled;
    using Widget::m_visible;
    using Base::m_label;
    using Base::m_value;
    using Base::notify;

    using scalar_type = typename VectorTraits<T>::scalar_type;
    static constexpr int N = VectorTraits<T>::N;
    static constexpr const char* default_format = DataTypeTraits<scalar_type>::default_format;

    Input(
        Widget* parent,
        std::string_view label = "",
        value_type value = value_type(0),
        Callback callback = {},
        scalar_type step = scalar_type(1),
        scalar_type step_fast = scalar_type(100),
        std::string_view format = default_format,
        InputTextFlags flags = InputTextFlags::none
    )
        : Base(parent, label, value, callback)
        , m_step(step)
        , m_step_fast(step_fast)
        , m_format(format)
        , m_flags(flags)
    {
    }

    scalar_type step() const { return m_step; }
    void set_step(scalar_type step) { m_step = step; }

    scalar_type step_fast() const { return m_step_fast; }
    void set_step_fast(scalar_type step_fast) { m_step_fast = step_fast; }

    const std::string& format() const { return m_format; }
    void set_format(std::string_view format) { m_format = format; }

    InputTextFlags flags() const { return m_flags; }
    void set_flags(InputTextFlags flags) { m_flags = flags; }

    virtual void render() override
    {
        if (!m_visible)
            return;

        ScopedID id(this);
        ScopedDisable disable(!m_enabled);
        bool changed = ImGui::InputScalarN(
            m_label.c_str(),
            DataTypeTraits<scalar_type>::data_type,
            &m_value,
            N,
            &m_step,
            &m_step_fast,
            m_format.c_str(),
            ImGuiInputTextFlags(m_flags)
        );
        if (changed)
            notify();
    }

private:
    scalar_type m_step;
    scalar_type m_step_fast;
    std::string m_format;
    InputTextFlags m_flags;
};

using InputFloat = Input<float>;
using InputFloat2 = Input<float2>;
using InputFloat3 = Input<float3>;
using InputFloat4 = Input<float4>;
using InputInt = Input<int>;
using InputInt2 = Input<int2>;
using InputInt3 = Input<int3>;
using InputInt4 = Input<int4>;

class SGL_API InputText : public ValueProperty<std::string> {
    SGL_OBJECT(InputText)
public:
    using Base = ValueProperty<std::string>;

    InputText(
        Widget* parent,
        std::string_view label = "",
        std::string value = "",
        Callback callback = {},
        bool multi_line = false,
        InputTextFlags flags = InputTextFlags::none
    )
        : Base(parent, label, value, callback)
        , m_multi_line(multi_line)
        , m_flags(flags)
    {
    }

    virtual void render() override;

private:
    bool m_multi_line;
    InputTextFlags m_flags;
};

/// Displays a GPU texture using ImGui::Image.
///
/// The widget samples the texture directly through ImGui's renderer; no CPU
/// readback. Pass any \c sgl::Texture (e.g. the output of a slangpy compute
/// kernel) and it will be drawn at \c size pixels. If \c size has any zero
/// component the texture's mip-0 dimensions are used.
class SGL_API Image : public Widget {
    SGL_OBJECT(Image)
public:
    Image(
        Widget* parent,
        ref<Texture> texture = nullptr,
        float2 size = float2(0.f, 0.f),
        float2 uv0 = float2(0.f, 0.f),
        float2 uv1 = float2(1.f, 1.f)
    )
        : Widget(parent)
        , m_texture(texture)
        , m_size(size)
        , m_uv0(uv0)
        , m_uv1(uv1)
    {
    }

    ref<Texture> texture() const { return m_texture; }
    void set_texture(ref<Texture> texture) { m_texture = texture; }

    float2 size() const { return m_size; }
    void set_size(const float2& size) { m_size = size; }

    float2 uv0() const { return m_uv0; }
    void set_uv0(const float2& uv0) { m_uv0 = uv0; }

    float2 uv1() const { return m_uv1; }
    void set_uv1(const float2& uv1) { m_uv1 = uv1; }

    virtual void render() override;

private:
    ref<Texture> m_texture;
    float2 m_size;
    float2 m_uv0;
    float2 m_uv1;
};

/// Clickable image (ImGui::ImageButton). Like \c Image but behaves as a
/// button: invokes \c callback when clicked. Useful for texture-based
/// icon toolbars. \c size is the image size in points (excludes the
/// frame padding ImGui adds around it).
class SGL_API ImageButton : public Widget {
    SGL_OBJECT(ImageButton)
public:
    using Callback = std::function<void()>;

    ImageButton(
        Widget* parent,
        ref<Texture> texture = nullptr,
        float2 size = float2(0.f, 0.f),
        Callback callback = {},
        float2 uv0 = float2(0.f, 0.f),
        float2 uv1 = float2(1.f, 1.f)
    )
        : Widget(parent)
        , m_texture(texture)
        , m_size(size)
        , m_callback(callback)
        , m_uv0(uv0)
        , m_uv1(uv1)
    {
    }

    ref<Texture> texture() const { return m_texture; }
    void set_texture(ref<Texture> texture) { m_texture = texture; }

    float2 size() const { return m_size; }
    void set_size(const float2& size) { m_size = size; }

    float2 uv0() const { return m_uv0; }
    void set_uv0(const float2& uv0) { m_uv0 = uv0; }

    float2 uv1() const { return m_uv1; }
    void set_uv1(const float2& uv1) { m_uv1 = uv1; }

    Callback callback() const { return m_callback; }
    void set_callback(Callback callback) { m_callback = callback; }

    void notify()
    {
        if (m_callback)
            m_callback();
    }

    virtual void render() override;

private:
    ref<Texture> m_texture;
    float2 m_size;
    Callback m_callback;
    float2 m_uv0;
    float2 m_uv1;
};

/// Anchor used to place a plot's legend, mirroring ImPlotLocation_*.
/// Compass-direction names (north = top, south = bottom, etc.).
enum class LegendLocation : int {
    center = 0,
    north = 1 << 0,
    south = 1 << 1,
    west = 1 << 2,
    east = 1 << 3,
    north_west = north | west, // top-left
    north_east = north | east, // top-right (ImPlot default)
    south_west = south | west, // bottom-left
    south_east = south | east, // bottom-right
};

/// Real plotting via ImPlot. A single plot window with one or more line
/// series, configurable axes (label, range, autofit), legend, grid.
///
/// Usage:
///     plot = ui.Plot(parent, "frame time", x_label="frame", y_label="ms",
///                    size=(0, 280), autofit_y=True)
///     plot.add_line("ms", values_list)            # add or update a line
///     plot.set_y_limits(0.0, 33.0)                # optional manual limit
///
/// Each `add_line` call replaces the named series' data. Series keep their
/// label (used in the legend) and their values (a copy of the list).
class SGL_API Plot : public Widget {
    SGL_OBJECT(Plot)
public:
    Plot(
        Widget* parent,
        std::string_view label = "plot",
        std::string_view x_label = "",
        std::string_view y_label = "",
        float2 size = float2(-1.f, 200.f),
        bool autofit_x = true,
        bool autofit_y = true,
        LegendLocation legend_location = LegendLocation::north_west,
        bool legend_outside = false,
        bool legend_horizontal = false
    )
        : Widget(parent)
        , m_label(label)
        , m_x_label(x_label)
        , m_y_label(y_label)
        , m_size(size)
        , m_autofit_x(autofit_x)
        , m_autofit_y(autofit_y)
        , m_legend_location(legend_location)
        , m_legend_outside(legend_outside)
        , m_legend_horizontal(legend_horizontal)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view v) { m_label = v; }
    const std::string& x_label() const { return m_x_label; }
    void set_x_label(std::string_view v) { m_x_label = v; }
    const std::string& y_label() const { return m_y_label; }
    void set_y_label(std::string_view v) { m_y_label = v; }
    float2 size() const { return m_size; }
    void set_size(const float2& v) { m_size = v; }
    bool autofit_x() const { return m_autofit_x; }
    void set_autofit_x(bool v) { m_autofit_x = v; }
    bool autofit_y() const { return m_autofit_y; }
    void set_autofit_y(bool v) { m_autofit_y = v; }
    LegendLocation legend_location() const { return m_legend_location; }
    void set_legend_location(LegendLocation v) { m_legend_location = v; }
    bool legend_outside() const { return m_legend_outside; }
    void set_legend_outside(bool v) { m_legend_outside = v; }
    bool legend_horizontal() const { return m_legend_horizontal; }
    void set_legend_horizontal(bool v) { m_legend_horizontal = v; }

    void set_x_limits(float lo, float hi)
    {
        m_x_min = lo;
        m_x_max = hi;
        m_has_x_limits = true;
    }
    void set_y_limits(float lo, float hi)
    {
        m_y_min = lo;
        m_y_max = hi;
        m_has_y_limits = true;
    }
    void clear_limits() { m_has_x_limits = m_has_y_limits = false; }

    /// Per-series storage. Each series is either a line plot (ImPlot::PlotLine)
    /// or a histogram (ImPlot::PlotHistogram). The histogram-only fields are
    /// ignored for line series. `bins == -1` maps to ImPlotBin_Sturges
    /// (auto-binning); a positive integer is taken literally.
    enum class SeriesKind { line, histogram };
    struct Series {
        SeriesKind kind{SeriesKind::line};
        std::vector<float> values;
        int bins{-1}; // -1 -> ImPlotBin_Sturges
        double bar_scale{1.0};
    };

    /// Set or update a named line series. Stored by name; calling again
    /// with the same name replaces the values (and resets it to a line).
    void add_line(std::string_view name, std::vector<float> values)
    {
        std::string n(name);
        Series& s = m_series[n];
        s.kind = SeriesKind::line;
        s.values = std::move(values);
        if (std::find(m_series_order.begin(), m_series_order.end(), n) == m_series_order.end())
            m_series_order.push_back(n);
    }

    /// Set or update a named histogram series. Raw samples are passed in
    /// `values`; ImPlot bins them on render. `bins == -1` uses
    /// ImPlotBin_Sturges (auto). `bar_scale` widens or narrows the bars
    /// (1.0 = full bin width).
    void add_histogram(std::string_view name, std::vector<float> values, int bins = -1, double bar_scale = 1.0)
    {
        std::string n(name);
        Series& s = m_series[n];
        s.kind = SeriesKind::histogram;
        s.values = std::move(values);
        s.bins = bins;
        s.bar_scale = bar_scale;
        if (std::find(m_series_order.begin(), m_series_order.end(), n) == m_series_order.end())
            m_series_order.push_back(n);
    }

    /// Append a single sample to an existing series (rolls the buffer).
    /// Works for both line and histogram series.
    void push_to_line(std::string_view name, float value, size_t max_history = 0)
    {
        std::string n(name);
        Series& s = m_series[n];
        if (std::find(m_series_order.begin(), m_series_order.end(), n) == m_series_order.end())
            m_series_order.push_back(n);
        s.values.push_back(value);
        if (max_history > 0 && s.values.size() > max_history)
            s.values.erase(s.values.begin(), s.values.end() - max_history);
    }

    /// Set or replace the bar-groups overlay. Renders via
    /// ImPlot::PlotBarGroups: one bar per group (x position) with `labels.size()`
    /// segments per bar. If `stacked` is true segments stack to a column,
    /// otherwise they sit side-by-side. `values_per_label[i]` is the series for
    /// label `i`, indexed by group.
    ///
    /// All inner vectors must have the same length (= group count); shorter
    /// ones are zero-padded on the fly at render time.
    void add_bar_groups(
        std::vector<std::string> labels,
        std::vector<std::vector<float>> values_per_label,
        double group_size = 0.67,
        bool stacked = false
    )
    {
        m_bar_groups_labels = std::move(labels);
        m_bar_groups_values = std::move(values_per_label);
        m_bar_groups_group_size = group_size;
        m_bar_groups_stacked = stacked;
        m_has_bar_groups = true;
    }

    void clear_bar_groups() { m_has_bar_groups = false; }

    void clear()
    {
        m_series.clear();
        m_series_order.clear();
        m_has_bar_groups = false;
    }

    virtual void render() override;

private:
    std::string m_label;
    std::string m_x_label;
    std::string m_y_label;
    float2 m_size;
    bool m_autofit_x;
    bool m_autofit_y;
    bool m_has_x_limits{false};
    bool m_has_y_limits{false};
    float m_x_min{0.f}, m_x_max{0.f};
    float m_y_min{0.f}, m_y_max{0.f};
    LegendLocation m_legend_location{LegendLocation::north_west};
    bool m_legend_outside{false};
    bool m_legend_horizontal{false};
    std::map<std::string, Series> m_series;
    std::vector<std::string> m_series_order;
    // Bar-groups overlay (PlotBarGroups). Stored separately from m_series
    // because it's a multi-series block, not a single named series.
    bool m_has_bar_groups{false};
    std::vector<std::string> m_bar_groups_labels;
    std::vector<std::vector<float>> m_bar_groups_values;
    double m_bar_groups_group_size{0.67};
    bool m_bar_groups_stacked{false};
};

/// Line plot of an in-memory float buffer (uses ImGui::PlotLines).
///
/// The internal buffer is a circular ring: \c push_value() rolls the newest
/// sample in at the right. Useful for FPS / frame-time graphs without a full
/// ImPlot dependency.
class SGL_API PlotLines : public Widget {
    SGL_OBJECT(PlotLines)
public:
    PlotLines(
        Widget* parent,
        std::string_view label = "",
        std::vector<float> values = {},
        std::string_view overlay = "",
        float scale_min = std::numeric_limits<float>::max(),
        float scale_max = std::numeric_limits<float>::max(),
        float2 size = float2(0.f, 80.f)
    )
        : Widget(parent)
        , m_label(label)
        , m_values(std::move(values))
        , m_overlay(overlay)
        , m_scale_min(scale_min)
        , m_scale_max(scale_max)
        , m_size(size)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    const std::vector<float>& values() const { return m_values; }
    void set_values(std::vector<float> values) { m_values = std::move(values); }

    /// Pop the front, push \c v at the back (rolling buffer).
    void push_value(float v)
    {
        if (m_values.empty()) {
            m_values.push_back(v);
        } else {
            std::rotate(m_values.begin(), m_values.begin() + 1, m_values.end());
            m_values.back() = v;
        }
    }

    const std::string& overlay() const { return m_overlay; }
    void set_overlay(std::string_view overlay) { m_overlay = overlay; }

    float scale_min() const { return m_scale_min; }
    void set_scale_min(float v) { m_scale_min = v; }

    float scale_max() const { return m_scale_max; }
    void set_scale_max(float v) { m_scale_max = v; }

    float2 size() const { return m_size; }
    void set_size(const float2& size) { m_size = size; }

    virtual void render() override;

private:
    std::string m_label;
    std::vector<float> m_values;
    std::string m_overlay;
    float m_scale_min;
    float m_scale_max;
    float2 m_size;
};

/// Editable color swatch (ImGui::ColorEdit3 / ColorEdit4).
class SGL_API ColorEdit3 : public ValueProperty<float3> {
    SGL_OBJECT(ColorEdit3)
public:
    using Base = ValueProperty<float3>;
    ColorEdit3(Widget* parent, std::string_view label = "", float3 value = float3(0.f), Callback callback = {})
        : Base(parent, label, value, callback)
    {
    }
    virtual void render() override;
};

class SGL_API ColorEdit4 : public ValueProperty<float4> {
    SGL_OBJECT(ColorEdit4)
public:
    using Base = ValueProperty<float4>;
    ColorEdit4(Widget* parent, std::string_view label = "", float4 value = float4(0.f), Callback callback = {})
        : Base(parent, label, value, callback)
    {
    }
    virtual void render() override;
};

/// Inline color picker block (ImGui::ColorPicker3 / ColorPicker4).
class SGL_API ColorPicker3 : public ValueProperty<float3> {
    SGL_OBJECT(ColorPicker3)
public:
    using Base = ValueProperty<float3>;
    ColorPicker3(Widget* parent, std::string_view label = "", float3 value = float3(0.f), Callback callback = {})
        : Base(parent, label, value, callback)
    {
    }
    virtual void render() override;
};

class SGL_API ColorPicker4 : public ValueProperty<float4> {
    SGL_OBJECT(ColorPicker4)
public:
    using Base = ValueProperty<float4>;
    ColorPicker4(Widget* parent, std::string_view label = "", float4 value = float4(0.f), Callback callback = {})
        : Base(parent, label, value, callback)
    {
    }
    virtual void render() override;
};

/// Full-viewport dock space. Add this to the Screen and dock Window widgets
/// onto it (drag a window's title bar onto the central node, or use
/// \c Window.dock_id() / set_dock_id() for programmatic docking).
///
/// To set up a split layout programmatically, call \c request_split_horizontal
/// (or \c request_split_vertical), then on the next render the two child node
/// ids are populated; assign them to two windows via \c Window.set_dock_id.
class SGL_API DockSpace : public Widget {
    SGL_OBJECT(DockSpace)
public:
    DockSpace(Widget* parent)
        : Widget(parent)
    {
    }

    /// Root dock node id. Populated after the first render.
    uint32_t dock_id() const { return m_dock_id; }
    /// Left / right child node ids after a horizontal split (or top / bottom
    /// after a vertical one). Populated once the requested split has been
    /// applied. Zero until then.
    uint32_t left_dock_id() const { return m_left_id; }
    uint32_t right_dock_id() const { return m_right_id; }

    /// Request the next render to (re)build a left/right split where the left
    /// pane occupies \c ratio of the width. Causes any existing layout
    /// for this dockspace to be reset.
    void request_split_horizontal(float ratio)
    {
        m_split_dir = SplitDir::Horizontal;
        m_split_ratio = ratio;
    }

    /// Same as above but top/bottom (left = top, right = bottom).
    void request_split_vertical(float ratio)
    {
        m_split_dir = SplitDir::Vertical;
        m_split_ratio = ratio;
    }

    /// Make the central dock node transparent so the surface (or whatever
    /// is rendered behind ImGui) shows through where no docked window
    /// covers it. Useful for rendering a slangpy compute output to the
    /// surface and overlaying floating control windows.
    bool passthru_central_node() const { return m_passthru; }
    void set_passthru_central_node(bool v) { m_passthru = v; }

    virtual void render() override;

private:
    enum class SplitDir { None, Horizontal, Vertical };
    uint32_t m_dock_id{0};
    uint32_t m_left_id{0};
    uint32_t m_right_id{0};
    SplitDir m_split_dir{SplitDir::None};
    float m_split_ratio{0.7f};
    bool m_passthru{false};
};

} // namespace sgl::ui
