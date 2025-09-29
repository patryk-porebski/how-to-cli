class HowToCli < Formula
  include Language::Python::Virtualenv

  desc "Ask LLMs how to do anything with terminal commands"
  homepage "https://github.com/patryk-porebski/how-to-cli"
  url "https://github.com/patryk-porebski/how-to-cli/archive/refs/tags/v0.0.4.tar.gz"
  sha256 "PUT_SHA256_HERE_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.11"

  def install
    # Create virtualenv in libexec
    venv = virtualenv_create(libexec, "python3.11")
    
    # Install the package using the standard method
    # This will use pip to install from the current directory
    venv.pip_install_and_link buildpath

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