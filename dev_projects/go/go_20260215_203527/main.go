package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é uma interface para a comunicação com o Go Agent API
type GoAgentClient interface {
	SendEvent(eventName string, eventData map[string]interface{}) error
}

// Integrator é um struct que implementa as interfaces JiraClient e GoAgentClient
type Integrator struct{}

// CreateIssue envia um evento para o Go Agent para criar uma nova issue no Jira
func (i *Integrator) CreateIssue(title string, description string) error {
	eventData := map[string]interface{}{
		"issueTitle": title,
		"description": description,
	}
	return i.SendEvent("create_issue", eventData)
}

// SendEvent envia um evento para o Go Agent
func (i *Integrator) SendEvent(eventName string, eventData map[string]interface{}) error {
	log.Printf("Sending event: %s with data: %+v\n", eventName, eventData)
	// Simulação de envio de evento ao Go Agent
	return nil
}

func main() {
	integrator := &Integrator{}

	err := integrator.CreateIssue("Test Issue", "This is a test issue for integration.")
	if err != nil {
		log.Fatalf("Failed to create issue: %v\n", err)
	}
}