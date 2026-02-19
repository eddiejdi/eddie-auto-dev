package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v5"
)

// JiraClient represents a client to interact with Jira API.
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new instance of JiraClient.
func NewJiraClient(username, password string) (*JiraClient, error) {
	config := &jira.Config{
		ServerURL: "https://your-jira-server.com",
	}
	tokenAuth := jira.BasicAuthTransport(username, password)
	client, err := jira.NewClient(config, tokenAuth)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}
	return &JiraClient{client}, nil
}

// CreateIssue creates a new issue in Jira.
func (jc *JiraClient) CreateIssue(summary, description string) (*jira.Issue, error) {
	fields := jira.Fields{
		Title:       summary,
		Description: description,
	}
	return jc.client.CreateIssue(fields)
}

// main is the entry point of the program.
func main() {
	username := "your-jira-username"
	password := "your-jira-password"

	jc, err := NewJiraClient(username, password)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := "New Test Issue"
	description := "This is a test issue created by Go Agent."
	issue, err := jc.CreateIssue(summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
	fmt.Printf("Created issue with ID: %s\n", issue.Key)
}