// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "sgl/ui/fwd.h"

#include "sgl/core/fwd.h"
#include "sgl/core/object.h"
#include "sgl/core/timer.h"

#include "sgl/device/fwd.h"
#include "sgl/device/formats.h"
#include "sgl/math/vector_types.h"

#include <map>

struct ImGuiContext;
struct ImDrawData;
struct ImFont;
struct ImTextureData;
struct ImGuiStyle;

namespace sgl::ui {

/// Mirror of ImGui's color-slot enum (ImGuiCol_), integer-compatible with it.
enum class Col : int {
    text,
    text_disabled,
    window_bg,
    child_bg,
    popup_bg,
    border,
    border_shadow,
    frame_bg,
    frame_bg_hovered,
    frame_bg_active,
    title_bg,
    title_bg_active,
    title_bg_collapsed,
    menu_bar_bg,
    scrollbar_bg,
    scrollbar_grab,
    scrollbar_grab_hovered,
    scrollbar_grab_active,
    check_mark,
    slider_grab,
    slider_grab_active,
    button,
    button_hovered,
    button_active,
    header,
    header_hovered,
    header_active,
    separator,
    separator_hovered,
    separator_active,
    resize_grip,
    resize_grip_hovered,
    resize_grip_active,
    input_text_cursor,
    tab_hovered,
    tab,
    tab_selected,
    tab_selected_overline,
    tab_dimmed,
    tab_dimmed_selected,
    tab_dimmed_selected_overline,
    docking_preview,
    docking_empty_bg,
    plot_lines,
    plot_lines_hovered,
    plot_histogram,
    plot_histogram_hovered,
    table_header_bg,
    table_border_strong,
    table_border_light,
    table_row_bg,
    table_row_bg_alt,
    text_link,
    text_selected_bg,
    tree_lines,
    drag_drop_target,
    drag_drop_target_bg,
    unsaved_marker,
    nav_cursor,
    nav_windowing_highlight,
    nav_windowing_dim_bg,
    modal_window_dim_bg,
};

/// Live wrapper around the active ImGui style; fields mirror ImGuiStyle in snake_case.
class SGL_API Style : public Object {
    SGL_OBJECT(Style)
public:
    explicit Style(ImGuiContext* imgui_context);

    /// Apply ImGui's built-in dark theme.
    void colors_dark();
    /// Apply ImGui's built-in light theme.
    void colors_light();
    /// Apply ImGui's built-in classic theme.
    void colors_classic();

    /// Read a single color slot. Returns an RGBA float4 in [0, 1].
    float4 get_color(Col c) const;
    /// Write a single color slot. RGBA float4 in [0, 1].
    void set_color(Col c, float4 value);

// Scalar/vector accessors, one pair per ImGuiStyle field (defined in ui.cpp).
#define SGL_UI_STYLE_FLOAT(name)                                                                                       \
    float name() const;                                                                                                \
    void set_##name(float v);
#define SGL_UI_STYLE_VEC2(name)                                                                                        \
    float2 name() const;                                                                                               \
    void set_##name(float2 v);
#define SGL_UI_STYLE_BOOL(name)                                                                                        \
    bool name() const;                                                                                                 \
    void set_##name(bool v);

    SGL_UI_STYLE_FLOAT(alpha)
    SGL_UI_STYLE_FLOAT(disabled_alpha)
    SGL_UI_STYLE_VEC2(window_padding)
    SGL_UI_STYLE_FLOAT(window_rounding)
    SGL_UI_STYLE_FLOAT(window_border_size)
    SGL_UI_STYLE_VEC2(window_min_size)
    SGL_UI_STYLE_VEC2(window_title_align)
    SGL_UI_STYLE_FLOAT(child_rounding)
    SGL_UI_STYLE_FLOAT(child_border_size)
    SGL_UI_STYLE_FLOAT(popup_rounding)
    SGL_UI_STYLE_FLOAT(popup_border_size)
    SGL_UI_STYLE_VEC2(frame_padding)
    SGL_UI_STYLE_FLOAT(frame_rounding)
    SGL_UI_STYLE_FLOAT(frame_border_size)
    SGL_UI_STYLE_VEC2(item_spacing)
    SGL_UI_STYLE_VEC2(item_inner_spacing)
    SGL_UI_STYLE_VEC2(cell_padding)
    SGL_UI_STYLE_VEC2(touch_extra_padding)
    SGL_UI_STYLE_FLOAT(indent_spacing)
    SGL_UI_STYLE_FLOAT(columns_min_spacing)
    SGL_UI_STYLE_FLOAT(scrollbar_size)
    SGL_UI_STYLE_FLOAT(scrollbar_rounding)
    SGL_UI_STYLE_FLOAT(grab_min_size)
    SGL_UI_STYLE_FLOAT(grab_rounding)
    SGL_UI_STYLE_FLOAT(log_slider_deadzone)
    SGL_UI_STYLE_FLOAT(tab_rounding)
    SGL_UI_STYLE_FLOAT(tab_border_size)
    SGL_UI_STYLE_FLOAT(tab_bar_border_size)
    SGL_UI_STYLE_FLOAT(tab_bar_overline_size)
    SGL_UI_STYLE_FLOAT(separator_text_border_size)
    SGL_UI_STYLE_VEC2(separator_text_align)
    SGL_UI_STYLE_VEC2(separator_text_padding)
    SGL_UI_STYLE_VEC2(button_text_align)
    SGL_UI_STYLE_VEC2(selectable_text_align)
    SGL_UI_STYLE_FLOAT(docking_separator_size)
    SGL_UI_STYLE_FLOAT(mouse_cursor_scale)
    SGL_UI_STYLE_BOOL(anti_aliased_lines)
    SGL_UI_STYLE_BOOL(anti_aliased_lines_use_tex)
    SGL_UI_STYLE_BOOL(anti_aliased_fill)
    SGL_UI_STYLE_FLOAT(curve_tessellation_tol)
    SGL_UI_STYLE_FLOAT(circle_tessellation_max_error)

#undef SGL_UI_STYLE_FLOAT
#undef SGL_UI_STYLE_VEC2
#undef SGL_UI_STYLE_BOOL

private:
    ImGuiContext* m_imgui_context;
    ImGuiStyle& imgui_style() const;
};

class SGL_API Context : public Object {
    SGL_OBJECT(Context)
public:
    Context(ref<Device> device);
    ~Context();

    /// The main screen widget.
    ref<Screen> screen() const { return m_screen; }

    /// Live ImGui style wrapper.
    ref<Style> style() const { return m_style; }

    ImFont* get_font(const char* name);

    /// Load and register a TTF font under \c name, rasterised at \c size px.
    /// \c is_default makes it the default font; \c merge overlays its glyphs onto
    /// the previous font (e.g. an icon font). Must be called before the first frame.
    void add_font(const char* name, const char* path, float size, bool is_default = false, bool merge = false);

    /// Apply a registered font to subsequent widgets (until pop_font).
    void push_font(const char* name);
    void pop_font();

    /// True if any interactive item is hovered (from the last frame).
    bool is_any_item_hovered();

    /// Measure the rendered size of \c text with the current font.
    float2 calc_text_size(const char* text);

    /// Begin a new ImGui frame and renders the main screen widget.
    /// ImGui widget calls are generally only valid between `begin_frame` and `end_frame`.
    /// \param width Render texture width
    /// \param height Render texture height
    /// \param window Window this UI context is rendered for (optional).
    void begin_frame(uint32_t width, uint32_t height, sgl::Window* window = nullptr);

    /// End the ImGui frame and renders the UI to the provided texture.
    /// \param texture_view Texture view to render to
    /// \param command_encoder Command encoder to encode commands to
    void end_frame(TextureView* texture_view, CommandEncoder* command_encoder);

    /// End the ImGui frame and renders the UI to the provided texture.
    /// \param texture Texture to render to
    /// \param command_encoder Command encoder to encode commands to
    void end_frame(Texture* texture, CommandEncoder* command_encoder);

    /// Render Dear ImGui draw data to the provided texture view.
    /// @param draw_data Dear ImGui draw data.
    /// @param texture_view Texture view to render to.
    /// @param command_encoder Command encoder used to record the render pass.
    void render_draw_data(const ImDrawData* draw_data, TextureView* texture_view, CommandEncoder* command_encoder);

    /// Render Dear ImGui draw data to the provided texture.
    /// @param draw_data Dear ImGui draw data.
    /// @param texture Texture to render to.
    /// @param command_encoder Command encoder used to record the render pass.
    void render_draw_data(const ImDrawData* draw_data, Texture* texture, CommandEncoder* command_encoder);

    /// Pass a keyboard event to the UI context.
    /// \param event Keyboard event
    /// \return Returns true if event was consumed.
    bool handle_keyboard_event(const KeyboardEvent& event);

    /// Pass a mouse event to the UI context.
    /// \param event Mouse event
    /// \return Returns true if event was consumed.
    bool handle_mouse_event(const MouseEvent& event);

private:
    // TODO: The frame count should not be hard-coded like this.
    // We should probably both control the number of buffers in the Context constructor
    // and pass in the frame to use in begin_frame().
    static constexpr uint32_t FRAME_COUNT = 4;

    enum class RenderMode {
        disabled,
        rasterizer,
        sw_rasterizer,
    };

    void init_rasterizer();
    void init_sw_rasterizer();

    RenderPipeline* get_render_pipeline(Format format);
    ComputePipeline* get_draw_triangles_pipeline(Format format);

    void draw(
        const ImDrawData* draw_data,
        Buffer* vertex_buffer,
        Buffer* index_buffer,
        TextureView* texture_view,
        CommandEncoder* command_encoder
    );

    void draw_sw(
        const ImDrawData* draw_data,
        Buffer* vertex_buffer,
        Buffer* index_buffer,
        TextureView* texture_view,
        CommandEncoder* command_encoder
    );

    ref<Device> m_device;
    ImGuiContext* m_imgui_context;

    ref<Screen> m_screen;

    uint32_t m_frame_index{0};
    Timer m_frame_timer;
    float2 m_last_display_size{0.f, 0.f};

    RenderMode m_render_mode{RenderMode::disabled};

    ref<Sampler> m_sampler;
    ref<Buffer> m_vertex_buffers[FRAME_COUNT];
    ref<Buffer> m_index_buffers[FRAME_COUNT];

    // Resources for the rasterizer pipeline.
    ref<InputLayout> m_input_layout;
    ref<ShaderProgram> m_render_program;
    std::map<Format, ref<RenderPipeline>> m_render_pipelines;

    // Resources for the SW rasterizer pipeline.
    ref<Buffer> m_triangle_buffer;
    ref<Buffer> m_bbox_buffer;
    ref<Buffer> m_tile_bitmask_buffer;
    ref<ComputePipeline> m_setup_triangles_pipeline;
    std::map<Format, ref<ComputePipeline>> m_draw_triangles_pipeline;

    ref<Style> m_style;
    std::map<std::string, ImFont*> m_fonts;
    std::map<ImTextureData*, ref<Texture>> m_textures;

    void update_texture(ImTextureData* tex);
    void update_mouse_cursor(sgl::Window* window);
};

} // namespace sgl::ui

// Extend ImGui with some additional convenience functions.
namespace ImGui {

SGL_API void PushFont(const char* name);

}
