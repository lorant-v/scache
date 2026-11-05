from scache.scache import SecretsCLI


def test_run():
  args = ["-v", "install"]
  SecretsCLI().run(args)
  assert 0


def test_diff():
  args = ["-v", "diff"]
  SecretsCLI().run(args)
  assert 0
