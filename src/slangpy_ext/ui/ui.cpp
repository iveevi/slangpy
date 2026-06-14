// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "nanobind.h"

#include "sgl/ui/ui.h"
#include "sgl/ui/widgets.h"

#include "sgl/core/error.h"
#include "sgl/core/input.h"
#include "sgl/core/window.h"

#include "sgl/device/device.h"
#include "sgl/device/command.h"
#include "sgl/device/fwd.h"

#include <imgui.h>
#include <imgui_internal.h>

#include <cstring>
#include <limits>
#include <memory>

#undef D
#define D(...) DOC(sgl, ui, __VA_ARGS__)

namespace sgl {

template<>
struct GcHelper<ui::Context> {
    void traverse(ui::Context*, GcVisitor& visitor) { visitor("screen"); }
    void clear(ui::Context*) { }
};

} // namespace sgl

namespace {

// Owns the temporary ImDrawList instances referenced by draw_data.CmdLists.
struct MarshaledDrawData {
    ImDrawListSharedData shared_draw_list_data;
    std::vector<std::unique_ptr<ImDrawList>> owned_draw_lists;
    ImDrawData draw_data;
};

MarshaledDrawData marshal_draw_data(nb::handle draw_data_obj)
{
    using namespace sgl;

    MarshaledDrawData result;

    nb::object cmd_lists = draw_data_obj.attr("cmd_lists");
    const size_t cmd_list_count = nb::len(cmd_lists);
    if (cmd_list_count > static_cast<size_t>(std::numeric_limits<int>::max())) {
        SGL_THROW("External ImGui draw-list count exceeds Dear ImGui limits: {}", cmd_list_count);
    }
    result.owned_draw_lists.reserve(cmd_list_count);
    result.draw_data.CmdLists.reserve(static_cast<int>(cmd_list_count));

    uint32_t index_size = sizeof(uint32_t);
    nb::object imgui_mod = draw_data_obj.type().attr("__module__");
    nb::object mod = nb::module_::import_(nb::cast<const char*>(imgui_mod));
    if (nb::hasattr(mod, "INDEX_SIZE"))
        index_size = nb::cast<uint32_t>(mod.attr("INDEX_SIZE"));
    if (index_size != 2 && index_size != 4)
        SGL_THROW("Unsupported external ImGui index size: {}", index_size);

    uint64_t total_vtx_count = 0;
    uint64_t total_idx_count = 0;

    for (nb::handle cmd_list_handle : cmd_lists) {
        nb::object cmd_buffer = cmd_list_handle.attr("cmd_buffer");
        nb::object vtx_buffer = cmd_list_handle.attr("vtx_buffer");
        nb::object idx_buffer = cmd_list_handle.attr("idx_buffer");

        const uint32_t vertex_count = nb::cast<uint32_t>(vtx_buffer.attr("size")());
        const uint32_t index_count = nb::cast<uint32_t>(idx_buffer.attr("size")());
        total_vtx_count += vertex_count;
        total_idx_count += index_count;

        auto draw_list = std::make_unique<ImDrawList>(&result.shared_draw_list_data);
        if (vertex_count > static_cast<uint32_t>(std::numeric_limits<int>::max()))
            SGL_THROW("External ImGui vertex count exceeds Dear ImGui limits: {}", vertex_count);
        draw_list->VtxBuffer.resize(static_cast<int>(vertex_count));
        if (vertex_count != 0) {
            const void* vertex_data
                = reinterpret_cast<const void*>(nb::cast<uintptr_t>(vtx_buffer.attr("data_address")()));
            if (vertex_data == nullptr)
                SGL_THROW("External ImGui vertex buffer contains null data");
            std::memcpy(draw_list->VtxBuffer.Data, vertex_data, size_t(vertex_count) * sizeof(ImDrawVert));
        }

        if (index_count > static_cast<uint32_t>(std::numeric_limits<int>::max()))
            SGL_THROW("External ImGui index count exceeds Dear ImGui limits: {}", index_count);
        draw_list->IdxBuffer.resize(static_cast<int>(index_count));
        if (index_count != 0) {
            const void* index_data
                = reinterpret_cast<const void*>(nb::cast<uintptr_t>(idx_buffer.attr("data_address")()));
            if (index_data == nullptr)
                SGL_THROW("External ImGui index buffer contains null data");

            if (index_size == sizeof(ImDrawIdx)) {
                std::memcpy(draw_list->IdxBuffer.Data, index_data, size_t(index_count) * sizeof(ImDrawIdx));
            } else if (index_size == 2) {
                const auto* src_indices = static_cast<const uint16_t*>(index_data);
                for (uint32_t index = 0; index < index_count; ++index)
                    draw_list->IdxBuffer.Data[index] = static_cast<ImDrawIdx>(src_indices[index]);
            } else {
                const auto* src_indices = static_cast<const uint32_t*>(index_data);
                for (uint32_t index = 0; index < index_count; ++index) {
                    const uint32_t src_index = src_indices[index];
                    if constexpr (sizeof(ImDrawIdx) < sizeof(uint32_t)) {
                        if (src_index > std::numeric_limits<ImDrawIdx>::max()) {
                            SGL_THROW(
                                "External ImGui index {} exceeds Dear ImGui index capacity {}",
                                src_index,
                                std::numeric_limits<ImDrawIdx>::max()
                            );
                        }
                    }
                    draw_list->IdxBuffer.Data[index] = static_cast<ImDrawIdx>(src_index);
                }
            }
        }

        const size_t command_count = nb::len(cmd_buffer);
        if (command_count > static_cast<size_t>(std::numeric_limits<int>::max()))
            SGL_THROW("External ImGui command count exceeds Dear ImGui limits: {}", command_count);

        draw_list->CmdBuffer.resize(static_cast<int>(command_count));
        if (command_count != 0) {
            std::memset(draw_list->CmdBuffer.Data, 0, command_count * sizeof(ImDrawCmd));

            size_t command_index = 0;
            for (nb::handle cmd_handle : cmd_buffer) {
                nb::object clip_rect = cmd_handle.attr("clip_rect");
                ImDrawCmd& draw_cmd = draw_list->CmdBuffer.Data[command_index++];
                draw_cmd.ClipRect = ImVec4(
                    nb::cast<float>(clip_rect.attr("x")),
                    nb::cast<float>(clip_rect.attr("y")),
                    nb::cast<float>(clip_rect.attr("z")),
                    nb::cast<float>(clip_rect.attr("w"))
                );
                draw_cmd.ElemCount = nb::cast<uint32_t>(cmd_handle.attr("elem_count"));
                draw_cmd.IdxOffset = nb::cast<uint32_t>(cmd_handle.attr("idx_offset"));
                draw_cmd.VtxOffset = nb::cast<uint32_t>(cmd_handle.attr("vtx_offset"));
                draw_cmd.TexRef = ImTextureRef(nb::cast<sgl::Texture*>(cmd_handle.attr("texture")));

                if (draw_cmd.IdxOffset > index_count || draw_cmd.ElemCount > index_count - draw_cmd.IdxOffset)
                    SGL_THROW("ImGui draw command index range exceeds its draw list");
                if (draw_cmd.VtxOffset > vertex_count)
                    SGL_THROW("ImGui draw command vertex offset exceeds its draw list");
                if (!draw_cmd.GetTexID())
                    SGL_THROW("ImGui draw command contains null texture");
                if (draw_cmd.ElemCount == 0)
                    continue;

                const ImDrawIdx* idx_base = draw_list->IdxBuffer.Data;
                for (uint32_t ei = 0; ei < draw_cmd.ElemCount; ++ei) {
                    const uint32_t index_val = idx_base[draw_cmd.IdxOffset + ei];
                    if (index_val + draw_cmd.VtxOffset >= vertex_count) {
                        SGL_THROW(
                            "ImGui draw command references out-of-bounds vertex: "
                            "index[{}]={} + vtx_offset={} >= vertex_count={}",
                            ei,
                            index_val,
                            draw_cmd.VtxOffset,
                            vertex_count
                        );
                    }
                }
            }
        }

        result.draw_data.CmdLists.push_back(draw_list.get());
        result.owned_draw_lists.push_back(std::move(draw_list));
    }

    nb::object display_pos = draw_data_obj.attr("display_pos");
    nb::object display_size = draw_data_obj.attr("display_size");
    nb::object framebuffer_scale = draw_data_obj.attr("framebuffer_scale");

    if (total_vtx_count > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
        SGL_THROW("External ImGui total vertex count exceeds Dear ImGui limits: {}", total_vtx_count);
    }
    if (total_idx_count > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
        SGL_THROW("External ImGui total index count exceeds Dear ImGui limits: {}", total_idx_count);
    }

    result.draw_data.Valid = true;
    result.draw_data.CmdListsCount = result.draw_data.CmdLists.Size;
    result.draw_data.TotalVtxCount = static_cast<int>(total_vtx_count);
    result.draw_data.TotalIdxCount = static_cast<int>(total_idx_count);
    result.draw_data.DisplayPos
        = ImVec2(nb::cast<float>(display_pos.attr("x")), nb::cast<float>(display_pos.attr("y")));
    result.draw_data.DisplaySize
        = ImVec2(nb::cast<float>(display_size.attr("x")), nb::cast<float>(display_size.attr("y")));
    result.draw_data.FramebufferScale
        = ImVec2(nb::cast<float>(framebuffer_scale.attr("x")), nb::cast<float>(framebuffer_scale.attr("y")));
    result.draw_data.OwnerViewport = nullptr;
    result.draw_data.Textures = nullptr;
    return result;
}

} // namespace

SGL_PY_EXPORT(ui)
{
    using namespace sgl;

    nb::module_ ui = nb::module_::import_("slangpy.ui");

    // ---- ImGui color slots (mirrors ImGuiCol_) ----
    nb::enum_<ui::Col>(ui, "Col")
        .value("text", ui::Col::text)
        .value("text_disabled", ui::Col::text_disabled)
        .value("window_bg", ui::Col::window_bg)
        .value("child_bg", ui::Col::child_bg)
        .value("popup_bg", ui::Col::popup_bg)
        .value("border", ui::Col::border)
        .value("border_shadow", ui::Col::border_shadow)
        .value("frame_bg", ui::Col::frame_bg)
        .value("frame_bg_hovered", ui::Col::frame_bg_hovered)
        .value("frame_bg_active", ui::Col::frame_bg_active)
        .value("title_bg", ui::Col::title_bg)
        .value("title_bg_active", ui::Col::title_bg_active)
        .value("title_bg_collapsed", ui::Col::title_bg_collapsed)
        .value("menu_bar_bg", ui::Col::menu_bar_bg)
        .value("scrollbar_bg", ui::Col::scrollbar_bg)
        .value("scrollbar_grab", ui::Col::scrollbar_grab)
        .value("scrollbar_grab_hovered", ui::Col::scrollbar_grab_hovered)
        .value("scrollbar_grab_active", ui::Col::scrollbar_grab_active)
        .value("check_mark", ui::Col::check_mark)
        .value("slider_grab", ui::Col::slider_grab)
        .value("slider_grab_active", ui::Col::slider_grab_active)
        .value("button", ui::Col::button)
        .value("button_hovered", ui::Col::button_hovered)
        .value("button_active", ui::Col::button_active)
        .value("header", ui::Col::header)
        .value("header_hovered", ui::Col::header_hovered)
        .value("header_active", ui::Col::header_active)
        .value("separator", ui::Col::separator)
        .value("separator_hovered", ui::Col::separator_hovered)
        .value("separator_active", ui::Col::separator_active)
        .value("resize_grip", ui::Col::resize_grip)
        .value("resize_grip_hovered", ui::Col::resize_grip_hovered)
        .value("resize_grip_active", ui::Col::resize_grip_active)
        .value("input_text_cursor", ui::Col::input_text_cursor)
        .value("tab_hovered", ui::Col::tab_hovered)
        .value("tab", ui::Col::tab)
        .value("tab_selected", ui::Col::tab_selected)
        .value("tab_selected_overline", ui::Col::tab_selected_overline)
        .value("tab_dimmed", ui::Col::tab_dimmed)
        .value("tab_dimmed_selected", ui::Col::tab_dimmed_selected)
        .value("tab_dimmed_selected_overline", ui::Col::tab_dimmed_selected_overline)
        .value("docking_preview", ui::Col::docking_preview)
        .value("docking_empty_bg", ui::Col::docking_empty_bg)
        .value("plot_lines", ui::Col::plot_lines)
        .value("plot_lines_hovered", ui::Col::plot_lines_hovered)
        .value("plot_histogram", ui::Col::plot_histogram)
        .value("plot_histogram_hovered", ui::Col::plot_histogram_hovered)
        .value("table_header_bg", ui::Col::table_header_bg)
        .value("table_border_strong", ui::Col::table_border_strong)
        .value("table_border_light", ui::Col::table_border_light)
        .value("table_row_bg", ui::Col::table_row_bg)
        .value("table_row_bg_alt", ui::Col::table_row_bg_alt)
        .value("text_link", ui::Col::text_link)
        .value("text_selected_bg", ui::Col::text_selected_bg)
        .value("tree_lines", ui::Col::tree_lines)
        .value("drag_drop_target", ui::Col::drag_drop_target)
        .value("drag_drop_target_bg", ui::Col::drag_drop_target_bg)
        .value("unsaved_marker", ui::Col::unsaved_marker)
        .value("nav_cursor", ui::Col::nav_cursor)
        .value("nav_windowing_highlight", ui::Col::nav_windowing_highlight)
        .value("nav_windowing_dim_bg", ui::Col::nav_windowing_dim_bg)
        .value("modal_window_dim_bg", ui::Col::modal_window_dim_bg);

    // ---- Live ImGuiStyle wrapper ----
    nb::class_<ui::Style, Object>(ui, "Style")
        .def("colors_dark", &ui::Style::colors_dark)
        .def("colors_light", &ui::Style::colors_light)
        .def("colors_classic", &ui::Style::colors_classic)
        .def("get_color", &ui::Style::get_color, "col"_a)
        .def("set_color", &ui::Style::set_color, "col"_a, "value"_a)
#define SGL_UI_STYLE_FLOAT_BIND(name) .def_prop_rw(#name, &ui::Style::name, &ui::Style::set_##name)
#define SGL_UI_STYLE_VEC2_BIND(name) .def_prop_rw(#name, &ui::Style::name, &ui::Style::set_##name)
#define SGL_UI_STYLE_BOOL_BIND(name) .def_prop_rw(#name, &ui::Style::name, &ui::Style::set_##name)
            SGL_UI_STYLE_FLOAT_BIND(alpha) SGL_UI_STYLE_FLOAT_BIND(disabled_alpha) SGL_UI_STYLE_VEC2_BIND(
                window_padding
            ) SGL_UI_STYLE_FLOAT_BIND(window_rounding) SGL_UI_STYLE_FLOAT_BIND(window_border_size)
                SGL_UI_STYLE_VEC2_BIND(window_min_size) SGL_UI_STYLE_VEC2_BIND(
                    window_title_align
                ) SGL_UI_STYLE_FLOAT_BIND(child_rounding) SGL_UI_STYLE_FLOAT_BIND(child_border_size)
                    SGL_UI_STYLE_FLOAT_BIND(popup_rounding) SGL_UI_STYLE_FLOAT_BIND(
                        popup_border_size
                    ) SGL_UI_STYLE_VEC2_BIND(frame_padding) SGL_UI_STYLE_FLOAT_BIND(frame_rounding)
                        SGL_UI_STYLE_FLOAT_BIND(frame_border_size) SGL_UI_STYLE_VEC2_BIND(
                            item_spacing
                        ) SGL_UI_STYLE_VEC2_BIND(item_inner_spacing) SGL_UI_STYLE_VEC2_BIND(cell_padding)
                            SGL_UI_STYLE_VEC2_BIND(touch_extra_padding) SGL_UI_STYLE_FLOAT_BIND(
                                indent_spacing
                            ) SGL_UI_STYLE_FLOAT_BIND(columns_min_spacing) SGL_UI_STYLE_FLOAT_BIND(scrollbar_size)
                                SGL_UI_STYLE_FLOAT_BIND(scrollbar_rounding) SGL_UI_STYLE_FLOAT_BIND(
                                    grab_min_size
                                ) SGL_UI_STYLE_FLOAT_BIND(grab_rounding) SGL_UI_STYLE_FLOAT_BIND(log_slider_deadzone)
                                    SGL_UI_STYLE_FLOAT_BIND(tab_rounding) SGL_UI_STYLE_FLOAT_BIND(tab_border_size)
                                        SGL_UI_STYLE_FLOAT_BIND(tab_bar_border_size) SGL_UI_STYLE_FLOAT_BIND(
                                            tab_bar_overline_size
                                        ) SGL_UI_STYLE_FLOAT_BIND(separator_text_border_size)
                                            SGL_UI_STYLE_VEC2_BIND(separator_text_align) SGL_UI_STYLE_VEC2_BIND(
                                                separator_text_padding
                                            ) SGL_UI_STYLE_VEC2_BIND(button_text_align)
                                                SGL_UI_STYLE_VEC2_BIND(selectable_text_align)
                                                    SGL_UI_STYLE_FLOAT_BIND(docking_separator_size)
                                                        SGL_UI_STYLE_FLOAT_BIND(mouse_cursor_scale)
                                                            SGL_UI_STYLE_BOOL_BIND(anti_aliased_lines)
                                                                SGL_UI_STYLE_BOOL_BIND(anti_aliased_lines_use_tex)
                                                                    SGL_UI_STYLE_BOOL_BIND(anti_aliased_fill)
                                                                        SGL_UI_STYLE_FLOAT_BIND(curve_tessellation_tol)
                                                                            SGL_UI_STYLE_FLOAT_BIND(
                                                                                circle_tessellation_max_error
                                                                            );
#undef SGL_UI_STYLE_FLOAT_BIND
#undef SGL_UI_STYLE_VEC2_BIND
#undef SGL_UI_STYLE_BOOL_BIND

    nb::class_<ui::Context, Object>(ui, "Context", gc_helper_type_slots<ui::Context>(), D(Context))
        .def(nb::init<ref<Device>>(), "device"_a)
        .def(
            "begin_frame",
            &ui::Context::begin_frame,
            "width"_a,
            "height"_a,
            "window"_a = nullptr,
            D(Context, begin_frame)
        )
        .def(
            "end_frame",
            nb::overload_cast<TextureView*, CommandEncoder*>(&ui::Context::end_frame),
            "texture_view"_a,
            "command_encoder"_a,
            D(Context, end_frame)
        )
        .def(
            "end_frame",
            nb::overload_cast<Texture*, CommandEncoder*>(&ui::Context::end_frame),
            "texture"_a,
            "command_encoder"_a,
            D(Context, end_frame, 2)
        )
        .def(
            "render_draw_data",
            [](ui::Context& self, nb::handle draw_data, TextureView* texture_view, CommandEncoder* command_encoder)
            {
                auto marshaled_draw_data = marshal_draw_data(draw_data);
                self.render_draw_data(&marshaled_draw_data.draw_data, texture_view, command_encoder);
            },
            nb::sig(
                "def render_draw_data(self, draw_data: object, texture_view: slangpy.TextureView, "
                "command_encoder: slangpy.CommandEncoder) -> None"
            ),
            "draw_data"_a,
            "texture_view"_a,
            "command_encoder"_a
        )
        .def(
            "render_draw_data",
            [](ui::Context& self, nb::handle draw_data, Texture* texture, CommandEncoder* command_encoder)
            {
                auto marshaled_draw_data = marshal_draw_data(draw_data);
                self.render_draw_data(&marshaled_draw_data.draw_data, texture, command_encoder);
            },
            nb::sig(
                "def render_draw_data(self, draw_data: object, texture: slangpy.Texture, "
                "command_encoder: slangpy.CommandEncoder) -> None"
            ),
            "draw_data"_a,
            "texture"_a,
            "command_encoder"_a
        )
        .def("handle_keyboard_event", &ui::Context::handle_keyboard_event, "event"_a, D(Context, handle_keyboard_event))
        .def("handle_mouse_event", &ui::Context::handle_mouse_event, "event"_a, D(Context, handle_mouse_event))
        .def(
            "add_font",
            &ui::Context::add_font,
            "name"_a,
            "path"_a,
            "size"_a,
            "is_default"_a = false,
            "merge"_a = false
        )
        .def("push_font", &ui::Context::push_font, "name"_a)
        .def("pop_font", &ui::Context::pop_font)
        .def("is_any_item_hovered", &ui::Context::is_any_item_hovered)
        .def("calc_text_size", &ui::Context::calc_text_size, "text"_a)
        .def_prop_ro("screen", &ui::Context::screen, D(Context, screen))
        .def_prop_ro("style", &ui::Context::style);
}
