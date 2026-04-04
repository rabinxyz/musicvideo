from musicvid.pipeline.logo_overlay import compute_margin, compute_logo_size, get_logo_position


class TestComputeMargin:
    def test_1920x1080(self):
        assert compute_margin(1920, 1080) == 54

    def test_1080x1920_portrait(self):
        assert compute_margin(1080, 1920) == 54

    def test_1080x1080_square(self):
        assert compute_margin(1080, 1080) == 54

    def test_3840x2160_4k(self):
        assert compute_margin(3840, 2160) == 108


class TestComputeLogoSize:
    def test_auto_1920x1080(self):
        w, h = compute_logo_size(1920, 1080, 100, 50)
        assert w == 230
        # height scaled proportionally: 50 * (230/100) = 115
        assert h == 115

    def test_auto_1080x1920_portrait(self):
        w, h = compute_logo_size(1080, 1920, 100, 50)
        assert w == 129
        assert h == 64

    def test_explicit_size(self):
        w, h = compute_logo_size(1920, 1080, 100, 50, requested_size=200)
        assert w == 200
        assert h == 100

    def test_auto_1080x1080_square(self):
        w, h = compute_logo_size(1080, 1080, 100, 50)
        assert w == 129
        assert h == 64


class TestGetLogoPosition:
    def test_top_left_1080p(self):
        x, y = get_logo_position("top-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 54

    def test_top_right_1080p(self):
        x, y = get_logo_position("top-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 54

    def test_bottom_left_1080p(self):
        x, y = get_logo_position("bottom-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 1080 - 100 - 54

    def test_bottom_right_1080p(self):
        x, y = get_logo_position("bottom-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 1080 - 100 - 54

    def test_portrait(self):
        x, y = get_logo_position("top-left", (130, 65), (1080, 1920))
        assert x == 54
        assert y == 54

    def test_4k(self):
        x, y = get_logo_position("top-left", (400, 200), (3840, 2160))
        assert x == 108
        assert y == 108
