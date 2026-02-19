package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma interface para o Go Agent
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraIntegration implementa a integração com o Jira
type JiraIntegration struct {
	client JiraClient
}

func (j *JiraIntegration) CreateIssue(title, description string) error {
	// Simulação de criação de issue no Jira
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

// GoAgentIntegration implementa a integração com o Go Agent
type GoAgentIntegration struct {
	client GoAgentClient
}

func (g *GoAgentIntegration) SendStatus(status string) error {
	// Simulação de envio de status ao Go Agent
	fmt.Printf("Sending status: %s\n", status)
	return nil
}

// Main é a função principal do programa
func main() {
	jira := &JiraIntegration{}
	goAgent := &GoAgentIntegration{}

	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		log.Fatalf("Error creating issue: %v\n", err)
	}

	err = goAgent.SendStatus("Running")
	if err != nil {
		log.Fatalf("Error sending status: %v\n", err)
	}
}