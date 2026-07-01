// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "sgl/ui/widgets.h"
#include "sgl/ui/ui.h"

#include <imgui.h>
#include <imgui_internal.h>
#include <implot.h>

#include <algorithm>
#include <limits>

namespace sgl::ui {

void Widget::render()
{
    if (!m_visible)
        return;

    for (const auto& child : m_children)
        child->render();
}

void Screen::render()
{
    Widget::render();
}

void Window::render()
{
    if (!m_visible)
        return;

    // Constructor pos/size apply only until imgui.ini has a saved layout;
    // explicit set_position / set_size below always override.
    ImGui::SetNextWindowPos(ImVec2(m_position.x, m_position.y), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(m_size.x, m_size.y), ImGuiCond_FirstUseEver);

    if (m_set_position) {
        ImGui::SetNextWindowPos(ImVec2(m_position.x, m_position.y));
        m_set_position = false;
    }
    if (m_set_size) {
        ImGui::SetNextWindowSize(ImVec2(m_size.x, m_size.y));
        m_set_size = false;
    }
    if (m_set_dock_id) {
        ImGui::SetNextWindowDockID(m_dock_id, ImGuiCond_Always);
        m_set_dock_id = false;
    }

    ImGuiWindowFlags flags = 0;
    if (m_overlay) {
        // Chrome-less overlay. Omit NoBringToFrontOnFocus so it stays above the docked viewport.
        flags |= ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove
            | ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoNavFocus
            | ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings;
    } else if (!m_show_title_bar) {
        flags |= ImGuiWindowFlags_NoTitleBar;
        // NoTitleBar hides only the floating title bar; the dock tab strip is
        // suppressed via the window class here and LocalFlags after Begin().
        ImGuiWindowClass window_class;
        window_class.DockNodeFlagsOverrideSet = ImGuiDockNodeFlags_NoTabBar | ImGuiDockNodeFlags_NoDockingOverMe;
        ImGui::SetNextWindowClass(&window_class);
    }

    const bool push_padding = m_padding.x >= 0.f && m_padding.y >= 0.f;
    if (push_padding)
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(m_padding.x, m_padding.y));

    ScopedID id(this);
    if (ImGui::Begin(m_title.c_str(), &m_visible, flags)) {
        auto pos = ImGui::GetWindowPos();
        m_position = float2(pos.x, pos.y);
        auto size = ImGui::GetWindowSize();
        m_size = float2(size.x, size.y);
        auto avail = ImGui::GetContentRegionAvail();
        m_content_size = float2(avail.x, avail.y);

        if (!m_overlay && !m_show_title_bar) {
            if (ImGuiDockNode* node = ImGui::GetWindowDockNode()) {
                // Cast through int: mixing the private and public dock-node enums warns.
                node->LocalFlags |= (int)ImGuiDockNodeFlags_NoTabBar | (int)ImGuiDockNodeFlags_NoDockingSplit
                    | (int)ImGuiDockNodeFlags_NoCloseButton;
                node->WantHiddenTabBarUpdate = true;
            }
        }

        const bool pushed_font = !m_font.empty();
        if (pushed_font)
            ImGui::PushFont(m_font.c_str());
        ImGui::PushItemWidth(300);
        Widget::render();
        ImGui::PopItemWidth();
        if (pushed_font)
            ImGui::PopFont();
    }
    ImGui::End();

    if (push_padding)
        ImGui::PopStyleVar();
}

void Group::render()
{
    if (!m_visible)
        return;

    bool nested = false;
    for (Widget* p = parent(); p != nullptr; p = p->parent())
        if (dynamic_cast<Group*>(p) != nullptr)
            nested = true;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);

    if (nested ? ImGui::TreeNodeEx(m_label.c_str(), ImGuiTreeNodeFlags_DefaultOpen)
               : ImGui::CollapsingHeader(m_label.c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
        Widget::render();
        if (nested)
            ImGui::TreePop();
    }
}

void TreeNode::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);

    if (m_set_open) {
        ImGui::SetNextItemOpen(m_open);
        m_set_open = false;
    }

    bool node_open = ImGui::TreeNodeEx(m_label.c_str(), ImGuiTreeNodeFlags_None);
    m_open = node_open;
    if (node_open) {
        Widget::render();
        ImGui::TreePop();
    }
}

void Table::render()
{
    if (!m_visible)
        return;
    if (m_columns < 1)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);

    ImGuiTableFlags flags = ImGuiTableFlags_SizingStretchProp;
    if (m_borders)
        flags |= ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg;

    if (ImGui::BeginTable(m_label.empty() ? "##table" : m_label.c_str(), m_columns, flags)) {
        if (!m_headers.empty()) {
            for (int i = 0; i < m_columns; ++i)
                ImGui::TableSetupColumn(i < int(m_headers.size()) ? m_headers[i].c_str() : "");
            ImGui::TableHeadersRow();
        }
        int col = 0;
        for (const auto& child : m_children) {
            if (col == 0)
                ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(col);
            child->render();
            col = (col + 1) % m_columns;
        }
        ImGui::EndTable();
    }
}

void Text::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    ImGui::TextUnformatted(m_text.c_str());
}

void Selectable::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    const bool indented = m_indent != 0.f;
    if (indented)
        ImGui::Indent(m_indent);
    const bool clicked = ImGui::Selectable(m_label.c_str(), m_selected, ImGuiSelectableFlags_SpanAvailWidth);
    if (indented)
        ImGui::Unindent(m_indent);
    if (clicked)
        notify();
}

void Separator::render()
{
    if (!m_visible)
        return;
    if (m_label.empty())
        ImGui::Separator();
    else
        ImGui::SeparatorText(m_label.c_str());
}

void ProgressBar::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    ImGui::ProgressBar(m_fraction);
}

void Button::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    if (m_border) {
        // Visible 1px border (from the text colour) even when the global border size is 0.
        ImVec4 bc = ImGui::GetStyleColorVec4(ImGuiCol_Text);
        bc.w *= 0.7f;
        ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.0f);
        ImGui::PushStyleColor(ImGuiCol_Border, bc);
    }
    if (m_active) {
        const ImVec4 accent = ImGui::GetStyleColorVec4(ImGuiCol_HeaderActive);
        ImGui::PushStyleColor(ImGuiCol_Button, accent);
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, accent);
        ImGui::PushStyleColor(ImGuiCol_ButtonActive, accent);
    }
    if (ImGui::Button(m_label.c_str()))
        notify();
    if (m_active)
        ImGui::PopStyleColor(3);
    if (m_border) {
        ImGui::PopStyleColor();
        ImGui::PopStyleVar();
    }
}

void SameLine::render()
{
    if (!m_visible)
        return;
    ImGui::SameLine(m_offset_x, m_spacing);
}

void CursorPos::render()
{
    if (!m_visible)
        return;
    const ImVec2 start = ImGui::GetCursorStartPos();
    ImGui::SetCursorPos(ImVec2(start.x + m_pos.x, start.y + m_pos.y));
}

void MenuBar::render()
{
    if (!m_visible)
        return;
    ImFont* font = ImGui::GetIO().FontDefault;
    if (font)
        ImGui::PushFont(font);
    if (ImGui::BeginMainMenuBar()) {
        Widget::render();
        ImGui::EndMainMenuBar();
    }
    if (font)
        ImGui::PopFont();
}

void Menu::render()
{
    if (!m_visible)
        return;
    if (ImGui::BeginMenu(m_label.c_str(), m_enabled)) {
        Widget::render();
        ImGui::EndMenu();
    }
}

void MenuItem::render()
{
    if (!m_visible)
        return;
    if (ImGui::MenuItem(m_label.c_str(), nullptr, m_checked, m_enabled)) {
        if (m_callback)
            m_callback();
    }
}

void CheckBox::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    if (ImGui::Checkbox(m_label.c_str(), &m_value))
        notify();
}

void ComboBox::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    int item_count = static_cast<int>(m_items.size());
    const char* preview = (m_value >= 0 && m_value < item_count) ? m_items[m_value].c_str() : "";
    apply_width();
    if (ImGui::BeginCombo(m_label.c_str(), preview)) {
        for (int i = 0; i < item_count; i++) {
            bool is_selected = (m_value == i);
            if (ImGui::Selectable(m_items[i].c_str(), is_selected)) {
                m_value = i;
                notify();
            }
            if (is_selected)
                ImGui::SetItemDefaultFocus();
        }
        ImGui::EndCombo();
    }
}

void ListBox::render()
{
    if (!m_visible)
        return;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    if (ImGui::ListBox(
            m_label.c_str(),
            &m_value,
            [](void* user_data, int idx)
            {
                return static_cast<const ListBox*>(user_data)->m_items[idx].c_str();
            },
            this,
            int(m_items.size()),
            m_height_in_items
        )) {
        notify();
    }
}

void InputText::render()
{
    if (!m_visible)
        return;

    auto text_callback = [](ImGuiInputTextCallbackData* data)
    {
        auto self = static_cast<InputText*>(data->UserData);
        if (data->EventFlag == ImGuiInputTextFlags_CallbackResize) {
            self->m_value.resize(data->BufTextLen);
            data->Buf = self->m_value.data();
        }
        return 0;
    };

    ImGuiInputTextFlags flags = ImGuiInputTextFlags(m_flags) | ImGuiInputTextFlags_CallbackResize;

    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    bool changed = false;
    if (m_multi_line) {
        changed = ImGui::InputTextMultiline(
            m_label.c_str(),
            m_value.data(),
            m_value.capacity() + 1,
            ImVec2(0, 0),
            flags,
            text_callback,
            this
        );
    } else {
        changed = ImGui::InputText(m_label.c_str(), m_value.data(), m_value.capacity() + 1, flags, text_callback, this);
    }
    if (changed)
        notify();
}

void Image::render()
{
    if (!m_visible || !m_texture)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    // A non-positive size component fills the available region on that axis.
    ImVec2 avail = ImGui::GetContentRegionAvail();
    ImVec2 sz(m_size.x > 0.f ? m_size.x : avail.x, m_size.y > 0.f ? m_size.y : avail.y);
    if (sz.x <= 0.f || sz.y <= 0.f)
        return;
    ImGui::Image(
        reinterpret_cast<ImTextureID>(m_texture.get()),
        sz,
        ImVec2(m_uv0.x, m_uv0.y),
        ImVec2(m_uv1.x, m_uv1.y)
    );
}

void ImageButton::render()
{
    if (!m_visible || !m_texture || m_size.x <= 0.f || m_size.y <= 0.f)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    if (ImGui::ImageButton(
            "##image_button",
            reinterpret_cast<ImTextureID>(m_texture.get()),
            ImVec2(m_size.x, m_size.y),
            ImVec2(m_uv0.x, m_uv0.y),
            ImVec2(m_uv1.x, m_uv1.y)
        ))
        notify();
}

void Plot::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    if (ImPlot::BeginPlot(m_label.c_str(), ImVec2(m_size.x, m_size.y))) {
        ImPlotAxisFlags x_flags = m_autofit_x ? ImPlotAxisFlags_AutoFit : 0;
        ImPlotAxisFlags y_flags = m_autofit_y ? ImPlotAxisFlags_AutoFit : 0;
        ImPlot::SetupAxes(
            m_x_label.empty() ? nullptr : m_x_label.c_str(),
            m_y_label.empty() ? nullptr : m_y_label.c_str(),
            x_flags,
            y_flags
        );
        {
            // Map our enum to ImPlotLocation_ and toggle Outside.
            ImPlotLocation loc = static_cast<ImPlotLocation>(m_legend_location);
            ImPlotLegendFlags lf = 0;
            if (m_legend_outside)
                lf |= ImPlotLegendFlags_Outside;
            if (m_legend_horizontal)
                lf |= ImPlotLegendFlags_Horizontal;
            ImPlot::SetupLegend(loc, lf);
        }
        if (m_has_x_limits)
            ImPlot::SetupAxisLimits(ImAxis_X1, m_x_min, m_x_max, ImPlotCond_Always);
        if (m_has_y_limits)
            ImPlot::SetupAxisLimits(ImAxis_Y1, m_y_min, m_y_max, ImPlotCond_Always);
        for (const auto& name : m_series_order) {
            const Series& s = m_series.at(name);
            if (s.values.empty())
                continue;
            if (s.kind == SeriesKind::line) {
                ImPlot::PlotLine(name.c_str(), s.values.data(), static_cast<int>(s.values.size()));
            } else {
                // -1 = auto bin count.
                int bins = (s.bins < 0) ? ImPlotBin_Sturges : s.bins;
                ImPlot::PlotHistogram(
                    name.c_str(),
                    s.values.data(),
                    static_cast<int>(s.values.size()),
                    bins,
                    s.bar_scale
                );
            }
        }
        // Bar-groups overlay (PlotBarGroups).
        if (m_has_bar_groups && !m_bar_groups_labels.empty()) {
            int item_count = static_cast<int>(m_bar_groups_labels.size());
            int group_count = 0;
            for (const auto& v : m_bar_groups_values)
                group_count = std::max(group_count, static_cast<int>(v.size()));
            if (group_count > 0) {
                // Flatten item-major, zero-padding ragged series.
                std::vector<float> flat(static_cast<size_t>(item_count) * group_count, 0.f);
                for (int i = 0; i < item_count; ++i) {
                    const auto& src = m_bar_groups_values[i];
                    int n = std::min(group_count, static_cast<int>(src.size()));
                    for (int g = 0; g < n; ++g)
                        flat[static_cast<size_t>(i) * group_count + g] = src[g];
                }
                std::vector<const char*> label_ptrs(item_count);
                for (int i = 0; i < item_count; ++i)
                    label_ptrs[i] = m_bar_groups_labels[i].c_str();
                ImPlotBarGroupsFlags flags = m_bar_groups_stacked ? ImPlotBarGroupsFlags_Stacked : 0;
                ImPlot::PlotBarGroups(
                    label_ptrs.data(),
                    flat.data(),
                    item_count,
                    group_count,
                    m_bar_groups_group_size,
                    /*shift*/ 0.0,
                    flags
                );
            }
        }
        ImPlot::EndPlot();
    }
}

void PlotLines::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    const char* overlay = m_overlay.empty() ? nullptr : m_overlay.c_str();
    ImGui::PlotLines(
        m_label.c_str(),
        m_values.data(),
        static_cast<int>(m_values.size()),
        /*values_offset*/ 0,
        overlay,
        m_scale_min,
        m_scale_max,
        ImVec2(m_size.x, m_size.y)
    );
}

void ColorEdit3::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    if (ImGui::ColorEdit3(m_label.c_str(), &m_value.x))
        notify();
}

void ColorEdit4::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    if (ImGui::ColorEdit4(m_label.c_str(), &m_value.x))
        notify();
}

void ColorPicker3::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    if (ImGui::ColorPicker3(m_label.c_str(), &m_value.x))
        notify();
}

void ColorPicker4::render()
{
    if (!m_visible)
        return;
    ScopedID id(this);
    ScopedDisable disable(!m_enabled);
    apply_width();
    if (ImGui::ColorPicker4(m_label.c_str(), &m_value.x))
        notify();
}

void DockSpace::render()
{
    if (!m_visible)
        return;
    ImGuiDockNodeFlags flags = m_passthru ? ImGuiDockNodeFlags_PassthruCentralNode : ImGuiDockNodeFlags_None;
    ImGuiID id = ImGui::DockSpaceOverViewport(0, ImGui::GetMainViewport(), flags);
    m_dock_id = static_cast<uint32_t>(id);

    if (m_split_dir != SplitDir::None) {
        ImGui::DockBuilderRemoveNode(id);
        ImGui::DockBuilderAddNode(id, ImGuiDockNodeFlags_DockSpace);
        ImGui::DockBuilderSetNodeSize(id, ImGui::GetMainViewport()->Size);
        ImGuiID a = 0, b = 0;
        ImGuiDir dir = (m_split_dir == SplitDir::Horizontal) ? ImGuiDir_Left : ImGuiDir_Up;
        ImGui::DockBuilderSplitNode(id, dir, m_split_ratio, &a, &b);
        m_left_id = static_cast<uint32_t>(a);
        m_right_id = static_cast<uint32_t>(b);
        ImGui::DockBuilderFinish(id);
        m_split_dir = SplitDir::None;
    }
    Widget::render();
}

std::pair<uint32_t, uint32_t> DockSpace::split_node(uint32_t node, bool vertical, float ratio)
{
    ImGuiID first = 0, second = 0;
    ImGuiDir dir = vertical ? ImGuiDir_Up : ImGuiDir_Left;
    ImGui::DockBuilderSplitNode(static_cast<ImGuiID>(node), dir, ratio, &first, &second);
    ImGui::DockBuilderFinish(static_cast<ImGuiID>(m_dock_id));
    return {static_cast<uint32_t>(first), static_cast<uint32_t>(second)};
}

} // namespace sgl::ui
