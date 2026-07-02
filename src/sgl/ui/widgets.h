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
#include <utility>
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

    /// Render as a chrome-less, auto-sized overlay (no title bar, move, resize or docking).
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

    /// Inner padding. A negative component uses the style default; (0,0) lets content fill the window.
    float2 padding() const { return m_padding; }
    void set_padding(const float2& padding) { m_padding = padding; }

    /// Name of a font (registered via Context.add_font) for this window's content.
    /// Empty uses the default font.
    const std::string& font() const { return m_font; }
    void set_font(std::string_view font) { m_font = font; }

    /// Content region size, captured on the last render.
    float2 content_size() const { return m_content_size; }

    void show() { set_visible(true); }
    void close() { set_visible(false); }

    /// Dock onto the given node on the next render (0 to detach).
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
    std::string m_font;
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

/// Collapsible tree node with a programmatically controllable open state.
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

/// Table layout. Children are laid out into cells in row-major order across
/// \c columns columns. Optional column \c headers render a header row.
class SGL_API Table : public Widget {
    SGL_OBJECT(Table)
public:
    Table(
        Widget* parent,
        std::string_view label = "",
        int columns = 2,
        std::vector<std::string> headers = {},
        bool borders = true
    )
        : Widget(parent)
        , m_label(label)
        , m_columns(columns)
        , m_headers(std::move(headers))
        , m_borders(borders)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    int columns() const { return m_columns; }
    void set_columns(int columns) { m_columns = columns; }

    const std::vector<std::string>& headers() const { return m_headers; }
    void set_headers(std::vector<std::string> headers) { m_headers = std::move(headers); }

    bool borders() const { return m_borders; }
    void set_borders(bool borders) { m_borders = borders; }

    virtual void render() override;

private:
    std::string m_label;
    int m_columns{2};
    std::vector<std::string> m_headers;
    bool m_borders{true};
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

    /// Draw filled with the accent colour to show a selected/toggled state.
    bool active() const { return m_active; }
    void set_active(bool active) { m_active = active; }

    /// Draw with a 1px frame border even if the global border size is 0.
    bool border() const { return m_border; }
    void set_border(bool border) { m_border = border; }

    /// Name of a font (registered via Context.add_font) for this button's label.
    /// Empty uses the default font.
    const std::string& font() const { return m_font; }
    void set_font(std::string_view font) { m_font = font; }

    /// Render as a compact button (no vertical frame padding).
    bool small() const { return m_small; }
    void set_small(bool small) { m_small = small; }

    /// Pixel size for the label font. 0 inherits the current size.
    float font_size() const { return m_font_size; }
    void set_font_size(float size) { m_font_size = size; }

    /// Explicit button size. A zero component auto-sizes to the label; a negative
    /// component uses the current frame height (for square/row-aligned buttons).
    float2 size() const { return m_size; }
    void set_size(const float2& size) { m_size = size; }

    /// Right-align the button to the content region (with a small inset), so it
    /// sits in a consistent column regardless of the preceding item's width.
    bool align_right() const { return m_align_right; }
    void set_align_right(bool align_right) { m_align_right = align_right; }

    /// Per-button frame padding override. A negative component keeps the style
    /// default. Small symmetric padding centres an icon label tightly.
    float2 frame_padding() const { return m_frame_padding; }
    void set_frame_padding(const float2& padding) { m_frame_padding = padding; }

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
    bool m_small{false};
    std::string m_font;
    float m_font_size{0.f};
    float2 m_size{0.f, 0.f};
    bool m_align_right{false};
    float2 m_frame_padding{-1.f, -1.f};
};

/// Selectable text row that highlights when selected and fires a callback on click.
class SGL_API Selectable : public Widget {
    SGL_OBJECT(Selectable)
public:
    using Callback = std::function<void()>;

    Selectable(
        Widget* parent,
        std::string_view label = "",
        Callback callback = {},
        bool selected = false,
        float indent = 0.f
    )
        : Widget(parent)
        , m_label(label)
        , m_callback(callback)
        , m_selected(selected)
        , m_indent(indent)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    Callback callback() const { return m_callback; }
    void set_callback(Callback callback) { m_callback = callback; }

    bool selected() const { return m_selected; }
    void set_selected(bool selected) { m_selected = selected; }

    float indent() const { return m_indent; }
    void set_indent(float indent) { m_indent = indent; }

    void notify()
    {
        if (m_callback)
            m_callback();
    }

    virtual void render() override;

private:
    std::string m_label;
    Callback m_callback;
    bool m_selected{false};
    float m_indent{0.f};
};

/// Place the next sibling widget on the same line as the previous one.
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

/// Move the draw cursor relative to the window content origin to place the next widget.
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

/// Main menu bar pinned to the top of the viewport. Add \c Menu children.
class SGL_API MenuBar : public Widget {
    SGL_OBJECT(MenuBar)
public:
    MenuBar(Widget* parent)
        : Widget(parent)
    {
    }

    virtual void render() override;
};

/// Drop-down menu hosted in a \c MenuBar (or nested in another \c Menu).
class SGL_API Menu : public Widget {
    SGL_OBJECT(Menu)
public:
    Menu(Widget* parent, std::string_view label = "")
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

/// Clickable, optionally checkable item inside a \c Menu.
class SGL_API MenuItem : public Widget {
    SGL_OBJECT(MenuItem)
public:
    using Callback = std::function<void()>;

    MenuItem(Widget* parent, std::string_view label = "", Callback callback = {}, bool checked = false)
        : Widget(parent)
        , m_label(label)
        , m_callback(callback)
        , m_checked(checked)
    {
    }

    const std::string& label() const { return m_label; }
    void set_label(std::string_view label) { m_label = label; }

    bool checked() const { return m_checked; }
    void set_checked(bool checked) { m_checked = checked; }

    Callback callback() const { return m_callback; }
    void set_callback(Callback callback) { m_callback = callback; }

    virtual void render() override;

private:
    std::string m_label;
    Callback m_callback;
    bool m_checked;
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

    /// Item width in pixels. 0 uses the ImGui default (~65% of the window width);
    /// a negative value fills the content region (e.g. -FLT_MIN fills to the right edge).
    float width() const { return m_width; }
    void set_width(float width) { m_width = width; }

    void notify()
    {
        if (m_callback)
            m_callback(m_value);
    }

protected:
    void apply_width()
    {
        if (m_width != 0.f)
            ImGui::SetNextItemWidth(m_width);
    }

    std::string m_label;
    value_type m_value;
    Callback m_callback;
    float m_width{0.f};
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
        this->apply_width();
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
        this->apply_width();
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
        this->apply_width();
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

/// Displays a GPU texture. A zero \c size component uses the texture's mip-0 size.
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

/// Clickable image; invokes \c callback when clicked.
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

/// Plot legend anchor (mirrors ImPlotLocation_*).
enum class LegendLocation : int {
    center = 0,
    north = 1 << 0,
    south = 1 << 1,
    west = 1 << 2,
    east = 1 << 3,
    north_west = north | west,
    north_east = north | east,
    south_west = south | west,
    south_east = south | east,
};

/// Plot via ImPlot: one or more line/histogram series with configurable axes and legend.
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

    /// Per-series storage (line or histogram).
    enum class SeriesKind { line, histogram };
    struct Series {
        SeriesKind kind{SeriesKind::line};
        std::vector<float> values;
        int bins{-1}; // -1 = auto
        double bar_scale{1.0};
    };

    /// Set or replace a named line series.
    void add_line(std::string_view name, std::vector<float> values)
    {
        std::string n(name);
        Series& s = m_series[n];
        s.kind = SeriesKind::line;
        s.values = std::move(values);
        if (std::find(m_series_order.begin(), m_series_order.end(), n) == m_series_order.end())
            m_series_order.push_back(n);
    }

    /// Set or replace a named histogram series (\c bins -1 = auto).
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

    /// Append a sample to an existing series (rolling buffer).
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

    /// Set or replace the bar-groups overlay (ImPlot::PlotBarGroups).
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
    // Bar-groups overlay, stored apart from the named series.
    bool m_has_bar_groups{false};
    std::vector<std::string> m_bar_groups_labels;
    std::vector<std::vector<float>> m_bar_groups_values;
    double m_bar_groups_group_size{0.67};
    bool m_bar_groups_stacked{false};
};

/// Line plot of an in-memory float ring buffer (ImGui::PlotLines).
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

/// Full-viewport dock space. Dock Window widgets onto it via \c Window.dock_id.
class SGL_API DockSpace : public Widget {
    SGL_OBJECT(DockSpace)
public:
    DockSpace(Widget* parent)
        : Widget(parent)
    {
    }

    /// Root dock node id (valid after the first render).
    uint32_t dock_id() const { return m_dock_id; }
    /// Child node ids after a split (left/right, or top/bottom); 0 until applied.
    uint32_t left_dock_id() const { return m_left_id; }
    uint32_t right_dock_id() const { return m_right_id; }

    /// Rebuild a left/right split on the next render (left pane = \c ratio of width).
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

    /// Split an existing node, returning the two child ids (vertical = top/bottom,
    /// else left/right; \c ratio = the first child's fraction). Call inside a frame.
    std::pair<uint32_t, uint32_t> split_node(uint32_t node, bool vertical, float ratio);

    /// Make the central node transparent so content behind ImGui shows through.
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
