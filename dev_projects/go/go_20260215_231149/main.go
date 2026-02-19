package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SendEvent(eventName string, eventData map[string]interface{}) error
}

// JiraService implementa a interface JiraClient
type JiraService struct{}

func (js *JiraService) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira para criar um issue
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentService implementa a interface GoAgentClient
type GoAgentService struct{}

func (gas *GoAgentService) SendEvent(eventName string, eventData map[string]interface{}) error {
	// Simulação de chamada à API do Go Agent para enviar um evento
	fmt.Printf("Sending event '%s' with data: %v\n", eventName, eventData)
	return nil
}

// Main é a função principal que implementa o fluxo de integração
func main() {
	jiraClient := &JiraService{}
	goAgentClient := &GoAgentService{}

	issueTitle := "New Feature Request"
	issueDescription := "Implement a new feature in the application."

	err := jiraClient.CreateIssue(issueTitle, issueDescription)
	if err != nil {
		log.Fatalf("Failed to create Jira issue: %v", err)
	}

	eventName := "feature_request_created"
	eventData := map[string]interface{}{
		"issue_title": issueTitle,
		"description": issueDescription,
	}

	err = goAgentClient.SendEvent(eventName, eventData)
	if err != nil {
		log.Fatalf("Failed to send Go Agent event: %v", err)
	}
}