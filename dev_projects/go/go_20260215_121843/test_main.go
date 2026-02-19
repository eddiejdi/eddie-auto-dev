package main

import (
	"testing"
)

func TestJiraService_CreateIssue(t *testing.T) {
	jiraClient := &JiraService{}
	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("CreateIssue should not return an error, but got: %v", err)
	}
}

func TestGoAgentService_SendStatus(t *testing.T) {
	goAgentClient := &GoAgentService{}
	err := goAgentClient.SendStatus("In progress")
	if err != nil {
		t.Errorf("SendStatus should not return an error, but got: %v", err)
	}
}