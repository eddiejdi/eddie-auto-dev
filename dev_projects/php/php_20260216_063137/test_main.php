<?php

use PhpAgent\JiraClient;
use PhpAgent\JiraIssue;

// Teste para criar um novo issue no Jira
function testCreateJiraIssue() {
    $agent = new JiraClient('https://your-jira-instance.atlassian.net', 'username', 'password');

    try {
        // Função para criar um novo issue no Jira
        function createJiraIssue($projectKey, $summary, $description, $assignee) {
            $issue = new JiraIssue();
            $issue->setProjectKey($projectKey);
            $issue->setTitle($summary);
            $issue->setDescription($description);
            $issue->setAssignee($assignee);

            return $agent->createIssue($issue);
        }

        // Caso de sucesso com valores válidos
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'New task for the project';
        $description = 'This is a new task created by PHP Agent for Jira.';
        $assignee = 'user123';

        $newIssue = createJiraIssue($projectKey, $summary, $description, $assignee);
        assert($newIssue instanceof JiraIssue);
        assert($newIssue->getTitle() === $summary);
        assert($newIssue->getDescription() === $description);
        assert($newIssue->getAssignee() === $assignee);

        // Caso de erro (divisão por zero)
        try {
            createJiraIssue('YOUR_PROJECT_KEY', 'New task for the project', 'This is a new task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (valores inválidos)
        try {
            createJiraIssue('YOUR_PROJECT_KEY', '', 'This is a new task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (edge case: valor limite)
        try {
            createJiraIssue('YOUR_PROJECT_KEY', 'New task for the project', 'This is a new task created by PHP Agent for Jira.', 'user1234567890');
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }
    } catch (Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}

// Teste para atualizar um issue no Jira
function testUpdateJiraIssue() {
    $agent = new JiraClient('https://your-jira-instance.atlassian.net', 'username', 'password');

    try {
        // Função para atualizar um issue no Jira
        function updateJiraIssue($issueId, $summary, $description) {
            $issue = new JiraIssue();
            $issue->setId($issueId);
            $issue->setTitle($summary);
            $issue->setDescription($description);

            return $agent->updateIssue($issue);
        }

        // Caso de sucesso com valores válidos
        $issueId = 12345;
        $summary = 'Updated task for the project';
        $description = 'This is an updated task created by PHP Agent for Jira.';
        $updatedIssue = updateJiraIssue($issueId, $summary, $description);
        assert($updatedIssue instanceof JiraIssue);
        assert($updatedIssue->getTitle() === $summary);
        assert($updatedIssue->getDescription() === $description);

        // Caso de erro (divisão por zero)
        try {
            updateJiraIssue(12345, 'Updated task for the project', 'This is an updated task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (valores inválidos)
        try {
            updateJiraIssue(12345, '', 'This is an updated task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (edge case: valor limite)
        try {
            updateJiraIssue(12345, 'Updated task for the project', 'This is an updated task created by PHP Agent for Jira.', 'user1234567890');
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }
    } catch (Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}

// Teste para buscar um issue no Jira
function testGetJiraIssue() {
    $agent = new JiraClient('https://your-jira-instance.atlassian.net', 'username', 'password');

    try {
        // Função para buscar um issue no Jira
        function getJiraIssue($issueId) {
            return $agent->getIssue($issueId);
        }

        // Caso de sucesso com valores válidos
        $issueId = 12345;
        $issue = getJiraIssue($issueId);
        assert($issue instanceof JiraIssue);
        assert($issue->getId() === $issueId);

        // Caso de erro (divisão por zero)
        try {
            getJiraIssue(12345, 'Updated task for the project', 'This is an updated task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (valores inválidos)
        try {
            getJiraIssue(12345, '', 'This is an updated task created by PHP Agent for Jira.', null);
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }

        // Caso de erro (edge case: valor limite)
        try {
            getJiraIssue(12345, 'Updated task for the project', 'This is an updated task created by PHP Agent for Jira.', 'user1234567890');
            fail("Expected an exception to be thrown");
        } catch (\Exception $e) {
            assert($e instanceof \InvalidArgumentException);
        }
    } catch (Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}