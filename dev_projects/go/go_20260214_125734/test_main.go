package main

import (
	"testing"
)

// TestIntegrateJiraTest tests the Integrate method of JiraIntegration with a successful scenario
func TestIntegrateJiraTest(t *testing.T) {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}
	jiraIntegration := &JiraIntegration{jiraClient: jiraAPI, goAgentClient: goAgentAPI}

	err := jiraIntegration.Integrate()
	if err != nil {
		t.Errorf("Integrate should not return an error, but got %v", err)
	}
}

// TestIntegrateJiraErrorTest tests the Integrate method of JiraIntegration with an error scenario
func TestIntegrateJiraErrorTest(t *testing.T) {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}
	jiraIntegration := &JiraIntegration{jiraClient: jiraAPI, goAgentClient: goAgentAPI}

	err := jiraIntegration.Integrate()
	if err == nil {
		t.Errorf("Integrate should return an error, but got %v", err)
	}
}