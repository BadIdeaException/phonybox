# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.

def dev_dir
  current = Pathname.new(__dir__).realpath

  loop do
    candidate = current + ".dev"

    return candidate if candidate.directory? 

    parent = current.parent
    raise "Could not find .dev directory" if parent == current

    current = parent
  end
  current

end

Vagrant.configure("2") do |config|
  config.vm.provider "docker" do |docker|
    docker.image = "badideaexception/dev-env:26.04"
    docker.has_ssh = true
    docker.remains_running = true
    # Use project's directory name as name for the container.
    # (Note that this will fail if such a container already exists.)
    docker.name = File.dirname(__FILE__).split("/").last
    # Use container name as hostname inside the container, as is the default behavior for other providers.
    docker.create_args = ["--hostname", docker.name]
  end

  # Reflect host git user config in vm
  userconfig = `git config -l | grep user`
  config.vm.provision "shell", name: "Configure git user on VM to be the same as on the host", privileged: false, inline: <<-SHELL
    # Read ruby userconfig variable line by line
    while read -r line; do      
      if [[ ! -z $line ]]; then # Skip empty line at EOF
        key=${line%=*} # key is $line, up to the =
        val=${line#*=} # val is $line, after the =
      
        echo "Running command: git config --global --add $key $val"
        git config --global --add "$key" "$val"
      fi
    done < <(echo "#{userconfig}")
  SHELL
  config.ssh.forward_agent = true  
  config.vm.provision "file", source: "~/.ssh/", destination: "/home/vagrant/.ssh"
  config.vm.provision "file", source: "~/Programmieren/.dev/.gitignore", destination: "/home/vagrant/.gitignore"
  config.vm.provision "shell", name: "Install common system applications", inline: "apt-get install -y nano less git curl wget"
  config.vm.provision "shell", name: "Apply global gitignore", privileged: false, inline: "git config --global core.excludesFile 'home/vagrant/.gitignore'"
  config.vm.provision "shell", name: "Install python3 and pip", inline: "apt-get update && apt-get install -y python3 python3-pip"  
  config.vm.provision "shell", name: "Make python3 the default", inline: "apt-get install -y python-is-python3"
  config.vm.provision "shell", name: "Install poetry", privileged: false, inline: <<-SHELL
    # Install Poetry
    curl -sSL https://install.python-poetry.org | python3 -

    # Add Poetry to PATH in .bashrc if not already present
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' /home/vagrant/.bashrc; then
      echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/vagrant/.bashrc
    fi
  SHELL

  config.vm.provision "shell", name: "Install Ansible", inline: <<-SHELL
    apt-get install -y software-properties-common
    add-apt-repository --yes --update ppa:ansible/ansible
    apt-get install -y ansible
  SHELL

  config.vm.provision "shell", name: "Symlink ansible.cfg", inline: "ln -s /vagrant/provision/ansible.cfg /home/vagrant/.ansible.cfg"

  config.vm.provision "shell", name: "Install Spotify Soloist", inline: <<-SHELL
    mkdir -p /usr/local/lib/soloist
    curl -L https://soloist-builds.spotifycdn.com/soloist_release_x86_64.tar.gz | tar xz -C /usr/local/lib/soloist && ln -s /usr/local/lib/soloist/soloist /usr/local/bin/soloist
  SHELL
  
  config.ssh.username="vagrant"
  config.ssh.private_key_path = dev_dir + "vagrant.key"

  config.ssh.extra_args = ["-t", "cd /vagrant; bash --login"]
end
