<?php

use PhpAgent\Jira;
use Symfony\Component\Console\Application;

class JiraScrum15Test extends Application {
    public function __construct() {
        parent::__construct('Jira Scrum 15', '0.1');
    }

    protected function configure() {
        $this->addCommands([
            new JiraCommand(),
        ]);
    }
}

// Main entry point
if (php_sapi_name() === 'cli') {
    $app = new JiraScrum15Test();
    $exitCode = $app->run();
    exit($exitCode);
}