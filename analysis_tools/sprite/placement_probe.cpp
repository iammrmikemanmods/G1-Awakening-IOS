// Development-only adapter for original/native sprite placement comparison.
#include "g1/SpritePlacement.hpp"
#include <cstring>
#include <iostream>
#include <stdexcept>

static std::uint32_t bits(float value) {
    std::uint32_t result{};
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

int main() {
    try {
        std::size_t count{};
        if (!(std::cin >> count)) throw std::runtime_error("missing case count");
        for (std::size_t i = 0; i < count; ++i) {
            unsigned x{}, y{}, form{}, site{}, group{};
            std::int32_t dx{}, dy{};
            if (!(std::cin >> x >> y >> form >> dx >> dy >> site >> group) ||
                x > 255U || y > 255U || form > 255U || site > 1U || group > 1U)
                throw std::runtime_error("invalid placement input");
            const auto p = g1::make_unit_sprite_placement({std::uint8_t(x), std::uint8_t(y), std::uint8_t(form),
                                                         dx, dy, site != 0U, group != 0U});
            std::cout << "[[" << p.original_position[0] << ',' << p.original_position[1] << ','
                      << p.original_position[2] << "]," << bits(p.scale) << ",["
                      << bits(p.translation[0]) << ',' << bits(p.translation[1]) << ','
                      << bits(p.translation[2]) << "]," << bits(p.angle_degrees) << ",["
                      << bits(p.axis[0]) << ',' << bits(p.axis[1]) << ',' << bits(p.axis[2]) << "],[";
            for (std::size_t j = 0; j < p.model.size(); ++j) {
                if (j != 0U) std::cout << ',';
                std::cout << bits(p.model[j]);
            }
            std::cout << "]]\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
