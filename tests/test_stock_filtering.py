from pathlib import Path


class TestDirectorPromptFiltering:
    def test_director_prompt_bans_religious_keywords_in_search_query(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()
        for word in ["muslim", "mosque", "islamic", "hindu", "buddha",
                     "church interior", "cathedral", "shrine", "altar",
                     "rosary", "meditation", "prayer rug", "hijab"]:
            assert word in prompt_text.lower(), f"Missing banned word: {word}"

    def test_director_prompt_has_safe_query_guidance(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text().lower()
        assert "person sitting" in prompt_text or "person walking" in prompt_text
        assert "nature" in prompt_text

    def test_director_prompt_restricts_video_stock_to_nature(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()
        assert "TYPE_VIDEO_STOCK" in prompt_text
        assert "prayer" in prompt_text.lower() or "worship" in prompt_text.lower()
