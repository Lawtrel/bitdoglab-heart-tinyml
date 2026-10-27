#pragma once
#include <cstddef>
namespace pcg {
inline constexpr float kInputScale = 0.0431097969f;
inline constexpr float kOutputScale = 0.00390625f;
inline constexpr float kThreshold = 0.734675481f;
inline constexpr int kInputZero = -38, kOutputZero = -128;
inline constexpr std::size_t kArenaBytes = 147456;
inline constexpr char kModelSha256[] = "3b7e258e26ca124d9e973ba8b4ac5744c87c3ed1d41f501192d2ca7a0b185454";
}
