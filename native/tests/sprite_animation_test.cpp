#include "g1/SpriteAnimation.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
std::size_t checks{};
void check(bool condition, const char* message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F operation, const char* message) {
    bool rejected = false;
    try { operation(); } catch (const std::invalid_argument&) { rejected = true; }
      catch (const std::out_of_range&) { rejected = true; }
    check(rejected, message);
}
} // namespace

int main() {
    try {
        // Synthetic unequal durations distinguish the recovered single-duration
        // forward tick from a conventional animation sequencer.
        g1::SpriteAnimation a({{7, 100}, {8, 30}, {9, 200}});
        check(a.current_frame() == 7U && a.state().elapsed_ms == 0, "forward start");
        check(!a.advance_ms(99) && a.current_frame() == 7U, "before exact duration");
        check(a.advance_ms(1) && a.current_frame() == 8U && a.state().elapsed_ms == 0, "exact duration boundary");
        a.reset();
        check(a.advance_ms(250) && a.current_frame() == 9U && a.state().elapsed_ms == 50,
              "original entry-duration forward tick");
        a.reset();
        check(!a.advance_ms(300) && a.current_frame() == 7U && a.state().elapsed_ms == 0,
              "whole cycle leaves same final geometry");
        a.reset(1);
        check(a.advance_ms(300) && a.current_frame() == 9U && a.state().completed &&
              a.state().repeat_count == 1, "forward completion");
        check(!a.advance_ms(1000) && a.state().completed, "completed forward calls remain defined");
        a.reset(2);
        a.advance_ms(300);
        check(a.state().repeat_count == 1 && !a.state().completed && a.current_frame() == 7U,
              "finite forward repeat decrement");
        a.reset(0);
        a.advance_ms(300);
        check(!a.state().completed && a.current_frame() == 7U, "zero repeat loops forward");
        a.reset(-1, true);
        check(a.current_frame() == 9U && a.state().elapsed_ms == 200, "reverse start");
        check(!a.advance_ms(200) && a.current_frame() == 9U && a.state().elapsed_ms == 0,
              "reverse strict-negative boundary");
        check(a.advance_ms(1) && a.current_frame() == 8U && a.state().elapsed_ms == 29,
              "reverse reads entered duration");
        a.reset(-1, true);
        a.advance_ms(331);
        check(a.current_frame() == 9U && a.state().elapsed_ms == 199 && !a.state().completed,
              "reverse infinite wrap");
        a.reset(0, true);
        a.advance_ms(331);
        check(a.current_frame() == 7U && a.state().elapsed_ms == 99 && a.state().completed,
              "zero repeat completes reverse");
        a.reset(2, true);
        a.advance_ms(661);
        check(a.current_frame() == 7U && a.state().repeat_count == 1 && a.state().completed &&
              a.state().elapsed_ms == 99, "reverse finite repeat and completion");
        g1::SpriteAnimation single({{42, 1}}, -1, true);
        single.advance_ms(2'000'000'000U);
        check(single.current_frame() == 42U && single.state().elapsed_ms == 0 && !single.state().completed,
              "bounded computation for a large infinite reverse tick");
        rejects([] { g1::SpriteAnimation invalid({}); }, "empty sequence accepted");
        rejects([] { g1::SpriteAnimation invalid({{0, 0}}); }, "zero duration accepted");
        rejects([] { g1::SpriteAnimation invalid({{0, 32768}}); }, "negative original signed duration accepted");
        rejects([] { g1::SpriteAnimation invalid(std::vector<g1::AtlasStep>(256, {0, 1})); },
                "sequence beyond original count byte accepted");
        const auto before = a.state();
        rejects([&] { a.advance_ms(std::numeric_limits<std::uint32_t>::max()); }, "oversized delta accepted");
        check(a.state().elapsed_ms == before.elapsed_ms && a.state().step_index == before.step_index &&
              a.state().completed == before.completed, "rejected delta changed state");
        a.reset();
        a.advance_ms(99);
        rejects([&] { a.advance_ms(std::uint32_t(std::numeric_limits<std::int32_t>::max())); },
                "signed elapsed overflow accepted");
        check(a.current_frame() == 7U && a.state().elapsed_ms == 99, "overflow rejection changed state");
        std::cout << "Passed " << checks << " sprite animation checks; no original runtime required.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
