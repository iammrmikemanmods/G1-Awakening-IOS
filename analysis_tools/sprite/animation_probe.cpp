// Development-only stdin/stdout adapter for the native animation oracle.
// It links the portable native implementation, never original machine code.
#include "g1/SpriteAnimation.hpp"
#include <iostream>
#include <stdexcept>

static void state(const g1::SpriteAnimation& animation, bool changed) {
    const auto& s = animation.state();
    std::cout << '[' << s.step_index << ',' << unsigned(animation.current_frame()) << ','
              << s.elapsed_ms << ',' << s.repeat_count << ',' << s.reverse << ','
              << s.completed << ',' << changed << ']';
}

int main() {
    try {
        std::size_t count{};
        if (!(std::cin >> count)) throw std::runtime_error("missing case count");
        for (std::size_t c = 0; c < count; ++c) {
            std::size_t n{}, ticks{};
            std::int32_t repeats{};
            unsigned reversed{};
            if (!(std::cin >> n >> repeats >> reversed >> ticks) || n > 255U || reversed > 1U)
                throw std::runtime_error("invalid case header");
            std::vector<g1::AtlasStep> steps;
            for (std::size_t i = 0; i < n; ++i) {
                unsigned frame{}, duration{};
                if (!(std::cin >> frame >> duration) || frame > 255U || duration > 65535U)
                    throw std::runtime_error("invalid step");
                steps.push_back({std::uint8_t(frame), std::uint16_t(duration)});
            }
            g1::SpriteAnimation animation(std::move(steps), repeats, reversed != 0U);
            std::cout << '[';
            state(animation, true); // Original start always rebuilds geometry.
            for (std::size_t i = 0; i < ticks; ++i) {
                std::uint32_t delta{};
                if (!(std::cin >> delta)) throw std::runtime_error("missing delta");
                const auto changed = animation.advance_ms(delta);
                std::cout << ',';
                state(animation, changed);
            }
            std::cout << "]\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
