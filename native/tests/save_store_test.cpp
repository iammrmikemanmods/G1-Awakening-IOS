#include "g1/SaveStore.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <unistd.h> // Darwin declares mkdtemp here; Linux declares it in stdlib.

namespace {
std::size_t checks=0;
void check(bool value,const char* message) {
    ++checks;if(!value)throw std::runtime_error(message);
}
template<class Function> void rejects(Function f) {
    ++checks;try{f();}catch(const g1::FormatError&){return;}
    throw std::runtime_error("corrupt native profile accepted");
}
}

int main() {
    std::filesystem::path directory;
    try {
        g1::CampaignProfile profile;
        profile.completed[0]=true;profile.highest_unlocked={{17,6}};
        profile.records[0][16]={18,31,2};
        profile.records[1][5]={4,7,0};
        profile.records[1][7]={-1,std::numeric_limits<std::int32_t>::max(),
            std::numeric_limits<std::int32_t>::min()};
        const auto encoded=g1::encode_campaign_profile(profile);
        const auto decoded=g1::decode_campaign_profile(encoded);
        check(g1::encode_campaign_profile(decoded)==encoded,"profile format lost values");
        auto corrupt=encoded;corrupt[30]^=1;
        rejects([&]{g1::decode_campaign_profile(corrupt);});
        corrupt=encoded;corrupt.pop_back();
        rejects([&]{g1::decode_campaign_profile(corrupt);});
        corrupt=encoded;corrupt[8]=2;
        rejects([&]{g1::decode_campaign_profile(corrupt);});
        auto invalid=profile;invalid.records[0].pop_back();
        rejects([&]{g1::encode_campaign_profile(invalid);});
        invalid=profile;invalid.highest_unlocked[1]=9;
        rejects([&]{g1::encode_campaign_profile(invalid);});

        auto pattern=(std::filesystem::current_path()/"g1-save-test-XXXXXX").string();
        std::vector<char> name(pattern.begin(),pattern.end());name.push_back(0);
        const char* created=mkdtemp(name.data());
        if(!created)throw std::runtime_error("could not create isolated save test directory");
        directory=created;
        const auto destination=(directory/"campaign.g1native").string();
        auto result=g1::write_native_save_atomic(destination,encoded);
        check(result.succeeded && result.error.empty(),"first flushed atomic save failed");
        const auto reloaded=g1::decode_campaign_profile(g1::read_file(destination,4096));
        check(g1::encode_campaign_profile(reloaded)==encoded,"closed file reload lost profile state");
        profile.highest_unlocked[1]=7;profile.records[1][6]={9,4,1};
        const auto updated=g1::encode_campaign_profile(profile);
        result=g1::write_native_save_atomic(destination,updated);
        check(result.succeeded,"replacement flushed atomic save failed");
        check(g1::read_file(destination,4096)==updated,"replacement file retained old save data");
        result=g1::write_native_save_atomic((directory/"missing"/"campaign.g1native").string(),encoded);
        check(!result.succeeded && !result.error.empty(),"unwritable save was reported successful");
        check(g1::read_file(destination,4096)==updated,"failed write damaged previous save");
        const auto blocked=directory/"directory-target";std::filesystem::create_directory(blocked);
        result=g1::write_native_save_atomic(blocked.string(),encoded);
        check(!result.succeeded && std::filesystem::is_directory(blocked),"failed rename changed target");
        std::size_t leftovers=0;
        for(const auto& entry:std::filesystem::directory_iterator(directory))
            if(entry.path().filename().string().find(".writing-")!=std::string::npos)++leftovers;
        check(leftovers==0,"failed save left a temporary file");
        std::filesystem::remove_all(directory);directory.clear();
        std::cout<<checks<<" native profile/atomic file checks passed; iPhone cold reload remains untested\n";
    } catch(const std::exception& error) {
        if(!directory.empty())std::filesystem::remove_all(directory);
        std::cerr<<error.what()<<'\n';return 1;
    }
}
