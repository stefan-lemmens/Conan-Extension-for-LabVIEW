import os
from fnmatch import fnmatch
from xml.dom.minidom import parse
from conans import ConanFile, tools

class LabVIEWConanExtension(ConanFile):
    """custom conanfile implementation for LabVIEW packages
    see https://docs.conan.io/en/latest/reference/conanfile.html#conanfile-reference for more info

    IMPORTANT:
    conanfile.py recipes uses a variety of attributes and methods to operate. In order to avoid collisions and
    conflicts, follow these rules:
    - Public attributes and methods, like build(), self.package_folder, are reserved for Conan.
      Don’t use public members for custom fields or methods in the recipes.
    - Use “protected” access for your own members, like self._my_data or def _my_helper(self):.
      Conan only reserves “protected” members starting with _conan.
    """
    # REMARK:
    # The set_name() and set_version() methods are alternatives to the name and version attributes.
    # It is not advised or supported to define both a name attribute and a set_name() method.
    # Likewise, it is not advised or supported to define both a version attribute and a set_version() method.
    # If you define both, you may experience unexpected behavior.
    # https://docs.conan.io/en/latest/reference/conanfile/methods.html#set-name-set-version
    
    default_user = "user"
    default_channel = "stable"
    author = ""
    settings = "os", "build_type", "arch", "compiler"
    options = {"install_folder": "ANY"}
    default_options = {"install_folder": "Support"}
    no_copy_source = True
    giturl = ""

    def _find_project_file(self, projectpath):
        filename=''
        for filename in os.listdir(projectpath):
            if fnmatch(filename, '*.lvproj'):
                break
        return os.path.splitext(filename)[0]


    def _get_labview_version(self):
        domdoc = parse(os.path.join(self.source_folder, self._find_project_file(self.source_folder) + '.lvproj'))
        node = domdoc.getElementsByTagName('Project').pop(0)
        version = node.getAttribute('LVVersion')
        return '20' + version[0:2]


    def _labview_ci(self, command, parameters):
        lv_version = self._get_labview_version()
        g_cli_tools = 'C:\\Program Files (x86)\\National Instruments\\LabVIEW ' + lv_version + '\\vi.lib\\G CLI Tools\\'

        labview_command = 'g-cli'
        labview_command += ' --kill'
        labview_command += ' --lv-ver ' + lv_version
        labview_command += ' --timeout 60000 '
        labview_command += ' "' + os.path.join(g_cli_tools, command) + '"'
        labview_command += ' -- ' + parameters

        print(labview_command)
        return self.run(labview_command)

    def _run_vi_build(self):
        build_params = ' -Version "' + self.version + '"'
        build_params += ' -Branch "' + LabVIEWConanExtension.branch + '"'
        if LabVIEWConanExtension.branch != 'master':
            build_params += ' -Debug "True"'
        build_params += ' "' + os.path.join(self.source_folder, self._find_project_file(self.source_folder) + '.lvproj') + '"'
        print('Building version ' + self.version)
        result = self._labview_ci('LVBuild.vi', build_params)
        git = tools.Git(folder=self.source_folder)
        git.run('reset --hard')
        return result

    def set_name(self):
        """ConanFile Method override

        Dynamically define name atttribute in the recipe with this method.
        The following example (https://docs.conan.io/en/latest/reference/conanfile/methods.html#set-name-set-version)
        defines the package name reading it from a name.txt file and the version from the branch and commit of the
        recipe’s repository.

        These functions are executed after assigning the values of the name and version if they are provided
        from the command line.
        """
        self.name = self._find_project_file(self.recipe_folder).lower().replace(' ','_')

    def set_version(self):
        """ConanFile Method override

        Dynamically define version attribute in the recipe with this method.
        The following example (https://docs.conan.io/en/latest/reference/conanfile/methods.html#set-name-set-version)
        defines the package name reading it from a name.txt file and the version from the branch and commit of the
        recipe’s repository.

        These functions are executed after assigning the values of the name and version if they are provided
        from the command line.
        """
        git = tools.Git(folder=self.recipe_folder)
        try:
            LabVIEWConanExtension.branch = git.run('rev-parse --abbrev-ref HEAD')
        except:
            self.version = '0.0.0.1'
        else:
            tag = git.run('describe --tags --match "[0-9]*.[0-9]*.[0-9]*" --abbrev=0')
            current_commit = git.run('rev-parse HEAD')
            first_commit = git.run('rev-list --max-parents=0 HEAD')
            commit = git.run('rev-list --count ' + first_commit + ' ' + current_commit)
            if LabVIEWConanExtension.branch == 'master':
                self.version = tag + '.' + commit
            else:
                major, minor, fix = tag.split('.')
                self.version = '.'.join([major, minor, str(int(fix) + 1), commit])

    def package_id(self):
        """Creates a unique ID for the package. Default package ID is calculated using settings, options and
        requires properties. When a package creator specifies the values for any of those properties, it is
        telling that any value change will require a different binary package.
        
        Don't use the install folder to calculate the package id
        """
        del self.info.options.install_folder
    
    def source(self):
        """ConanFile Method override

        Method used to retrieve the source code from any other external origin like github using
        "$ git clone" or just a regular download.
        """
        git = tools.Git(folder=self.source_folder)
        git.clone(self.gitURL)
        git.checkout(LabVIEWConanExtension.branch)


    def build(self):
        """ConanFile Method override

        This method is used to build the source code of the recipe using the desired commands.
        You can use your command line tools to invoke your build system or any of
        the build helpers provided with Conan."""
        if self.settings.os == "Windows":
            self._run_vi_build()
        else:
            raise Exception("OS %s is not supported..." % (str(self.settings.os)))


    def package(self):
        """ConanFile Method override

        The actual creation of the package, once that it is built, is done in the package() method.
        Using the self.copy() method, artifacts are copied from the build folder to the package folder."""
        if self.settings.os == "Windows":
            self.copy("*", src=self.source_folder + "/Build", dst="lib", symlinks="True")
        else:
            raise Exception("OS %s is not supported..." % (str(self.settings.os)))


    def imports(self):
        """ConanFile Method override

        Importing files copies files from the local store to your project. This feature is handy for copying shared
        libraries (dylib in Mac, dll in Win) to the directory of your executable, so that you don’t have to mess with
        your PATH to run them. But there are other use cases:
        - Copy an executable to your project, so that it can be easily run. A good example is the Google’s protobuf
          code generator.
        - Copy package data to your project, like configuration, images, sounds… A good example is the
          OpenCV demo, in which face detection XML pattern files are required.

        Importing files is also very convenient in order to redistribute your application, as many times you will
        just have to bundle your project’s bin folder.
        """
        if self.in_local_cache:
            self.copy("*", src="lib", dst=self.source_folder + str(self.options.install_folder))
        else:
            self.copy("*", src="lib", dst=str(self.options.install_folder))
