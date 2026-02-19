package main_test

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of Scrum11Integrator
func TestCreateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	title := "New Task"
	description := "Implement Go Agent integration with Jira"

	err := integrator.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
}

// TestSendAlert tests the SendAlert method of Scrum11Integrator
func TestSendAlert(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	message := "Go Agent is down!"

	err := integrator.SendAlert(message)
	if err != nil {
		t.Errorf("SendAlert failed: %v", err)
	}
}

// TestCreateIssueError tests the CreateIssue method with an error case
func TestCreateIssueError(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	title := "New Task"
	description := ""

	err := integrator.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not return an error")
	}
}

// TestSendAlertError tests the SendAlert method with an error case
func TestSendAlertError(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	message := ""

	err := integrator.SendAlert(message)
	if err == nil {
		t.Errorf("SendAlert did not return an error")
	}
}

// TestCreateIssueEdgeCase tests the CreateIssue method with edge cases
func TestCreateIssueEdgeCase(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	title := ""
	description := "Implement Go Agent integration with Jira"

	err := integrator.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not return an error")
	}
}

// TestSendAlertEdgeCase tests the SendAlert method with edge cases
func TestSendAlertEdgeCase(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	integrator := NewScrum11Integrator(jiraClient, goAgentClient)

	title := "New Task"
	description := ""

	err := integrator.SendAlert(title)
	if err == nil {
		t.Errorf("SendAlert did not return an error")
	}
}