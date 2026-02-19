package main_test

import (
	"testing"
)

func TestJiraService_CreateIssue(t *testing.T) {
	jiraClient := &JiraService{}
	err := jiraClient.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		t.Errorf("Failed to create issue in Jira: %v\n", err)
	}
}

func TestGoAgentService_SendStatus(t *testing.T) {
	goAgentClient := &GoAgentService{}
	err := goAgentClient.SendStatus("Running")
	if err != nil {
		t.Errorf("Failed to send status to Go Agent: %v\n", err)
	}
}