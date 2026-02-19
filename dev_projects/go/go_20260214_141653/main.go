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

// JiraIntegration é uma implementação de JiraClient que faz chamadas ao Jira API
type JiraIntegration struct{}

func (j *JiraIntegration) CreateIssue(title string, description string) error {
	// Simulação da chamada à API do Jira
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentIntegration é uma implementação de GoAgentClient que faz chamadas ao Go Agent API
type GoAgentIntegration struct{}

func (g *GoAgentIntegration) SendEvent(eventName string, eventData map[string]interface{}) error {
	// Simulação da chamada à API do Go Agent
	fmt.Printf("Sending event '%s' with data: %v\n", eventName, eventData)
	return nil
}

// Main é a função principal que executa o programa
func main() {
	jiraClient := &JiraIntegration{}
	goAgentClient := &GoAgentIntegration{}

	issueTitle := "New Feature Request"
	issueDescription := "Implement a new feature to improve user experience"

	err := jiraClient.CreateIssue(issueTitle, issueDescription)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	eventName := "FeatureRequestCreated"
	eventData := map[string]interface{}{
		"issueTitle": issueTitle,
		"description": issueDescription,
	}

	err = goAgentClient.SendEvent(eventName, eventData)
	if err != nil {
		log.Fatalf("Failed to send event: %v", err)
	}
}