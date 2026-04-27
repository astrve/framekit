from framekit.core.paths import PathResolver


def test_resolve_start_folder_uses_explicit_path():
    settings = {
        "general": {"default_folder": ""},
        "modules": {"renamer": {"last_folder": "", "default_folder": ""}},
    }

    resolver = PathResolver(settings)
    result = resolver.resolve_start_folder("renamer", "/tmp/example")
    assert str(result).endswith("example")


def test_resolve_start_folder_uses_module_last_folder():
    settings = {
        "general": {"default_folder": "/tmp/global"},
        "modules": {"renamer": {"last_folder": "/tmp/last", "default_folder": "/tmp/module"}},
    }

    resolver = PathResolver(settings)
    result = resolver.resolve_start_folder("renamer")
    assert str(result).endswith("last")
