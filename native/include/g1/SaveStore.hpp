#pragma once

#include "g1/MissionProgression.hpp"

namespace g1 {

// Versioned native profile format. This does not claim compatibility with an
// original ARM object's serialized memory or with the old app's save files.
Bytes encode_campaign_profile(const CampaignProfile&);
CampaignProfile decode_campaign_profile(const Bytes&);

struct SaveWriteResult {
    bool succeeded{};
    std::string error;
};

// Writes a temporary sibling, flushes its contents, atomically renames it,
// then flushes the parent directory. Existing destination data is preserved
// on failures before rename. A later directory-flush error is still reported
// as failure so campaign handoff cannot silently assume durable persistence.
// The host creates/selects its app-private parent directory beforehand.
SaveWriteResult write_native_save_atomic(const std::string& destination,const Bytes&);

} // namespace g1
