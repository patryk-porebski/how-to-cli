class HowToCli < Formula
  include Language::Python::Virtualenv

  desc "Ask LLMs how to do anything with terminal commands"
  homepage "https://github.com/patryk-porebski/how-to-cli"
  url "https://github.com/patryk-porebski/how-to-cli/archive/refs/tags/v0.0.1.tar.gz"
  sha256 "PUT_SHA256_HERE_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.11"

  resource "click" do
    url "https://files.pythonhosted.org/packages/96/d3/f04c7bfcf5c1862a2a5b845c6b2b360488cf47af55dfa79c98f6a6bf98b5/click-8.1.7.tar.gz"
    sha256 "ca9853ad459e787e2192211578cc907e7594e294c7ccc834310722b41b9ca6de"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/9d/be/10918a2eac4ae9f02f6cfe6414b7a155ccd8f7f9d4380d62fd5b955065c3/requests-2.31.0.tar.gz"
    sha256 "942c5a758f98d5e8f5e3e0e7e8d4d8c1a3c4f9d9e6c7c19b1d5b6e3a4c8c5b6e"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/cd/e5/af35f7ea75cf72f2cd079c95ee16797de7cd71f29ea7c68ae5ce7be1eda0/PyYAML-6.0.1.tar.gz"
    sha256 "bfdf460b1736c775f2ba9f6a92bca30bc2095067b8a9d77876d1fad6cc3b4a43"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/b3/01/c954e134dc440ab5f96952fe52b4fdc64225530320a910473c1fe270d9aa/rich-13.7.0.tar.gz"
    sha256 "5cb5123b5cf9ee70584244246816e9114227e0b98ad9176eede6ad54bf5403fa"
  end

  resource "colorama" do
    url "https://files.pythonhosted.org/packages/d8/53/6f443c9a4a8358a93a6792e2acffb9d9d5cb0a5cfd8802644b7b1c9a02e4/colorama-0.4.6.tar.gz"
    sha256 "08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44"
  end

  resource "keyring" do
    url "https://files.pythonhosted.org/packages/63/95/357c7b5b97e3b71053d5fcb5c0c7e1661c3c6b7c8c8b1e3c9c3e5c3e6e7/keyring-24.3.0.tar.gz"
    sha256 "e730ecffd309658a08ee82535a3b5ec4b4c8b0c3c9b5e9e0c6e6f6e6c6e6c6e6"
  end

  resource "pyperclip" do
    url "https://files.pythonhosted.org/packages/a7/2c/4c64579f847bd5d539803c8b909e54ba087a79d01bb3aba433a95879a6c5/pyperclip-1.8.2.tar.gz"
    sha256 "105254a8b04934f0bc84e9c24eb360a591aaf6535c9def5f29d92af107a9bf57"
  end

  def install
    virtualenv_install_with_resources

    # Install shell completions
    bash_completion.install "completions/how_completion.bash" => "how"
    zsh_completion.install "completions/how_completion.zsh" => "_how"
    fish_completion.install "completions/how_completion.fish" => "how.fish"
  end

  def caveats
    <<~EOS
      To get started with How CLI:

      1. Initialize configuration:
         how config-init

      2. Set your OpenRouter API key:
         how config-set --key openrouter.api_key --value YOUR_API_KEY
         Or set the HOW_API_KEY environment variable

      3. Start using it:
         how to "install nodejs"

      Shell completion has been installed. You may need to restart your shell.
    EOS
  end

  test do
    assert_match "How", shell_output("#{bin}/how version")
  end
end
