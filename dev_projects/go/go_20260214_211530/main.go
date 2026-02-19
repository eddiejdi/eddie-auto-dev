package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient represents a client to interact with Jira API
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new instance of JiraClient
func NewJiraClient(apiKey, serverURL string) (*JiraClient, error) {
	jiraClient := &JiraClient{}
	config := jira.Config{
		Server:    serverURL,
		UserName: apiKey,
	}
	client, err := jira.New(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %w", err)
	}
	jiraClient.client = client
	return jiraClient, nil
}

// CreateIssue creates a new issue in Jira
func (jiraClient *JiraClient) CreateIssue(summary string, description string) (*jira.Issue, error) {
	fields := map[string]interface{}{
		"summary":  summary,
		"description": description,
	}
	newIssue, err := jiraClient.client.CreateIssue(fields)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %w", err)
	}
	return newIssue, nil
}

// Run the main function if this file is executed as the main program
func main() {
	apiKey := "your-jira-api-key"
	serverURL := "https://your-jira-server.atlassian.net"

	jiraClient, err := NewJiraClient(apiKey, serverURL)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := "Test issue created by Go Agent"
	description := "This is a test issue created using Go Agent."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	fmt.Printf("Created issue with ID: %s\n", newIssue.ID)
}