class Duster < Formula
  include Language::Python::Virtualenv

  desc "Installer for the Duster Codex plugin"
  homepage "https://github.com/injaneity/duster"
  url "https://github.com/injaneity/duster/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    libexec.install Dir["*"]
    (bin/"duster-plugin-install").write <<~EOS
      #!/bin/sh
      set -eu
      exec "#{Formula["python@3.12"].opt_bin}/python3" "#{libexec}/scripts/install_plugin.py" --source-root "#{libexec}" "$@"
    EOS
  end

  test do
    assert_match "usage", shell_output("#{bin}/duster-plugin-install --help")
  end
end
