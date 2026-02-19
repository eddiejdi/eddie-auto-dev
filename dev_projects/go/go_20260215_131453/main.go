package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o sistema Jira.
type JiraClient interface {
	CreateIssue(title string, description string) error
	UpdateIssue(issueID int, title string, description string) error
}

// GoAgentClient representa a interface para interagir com o Go Agent.
type GoAgentClient interface {
	SendMetric(metricName string, value float64) error
}

// Jira implements the JiraClient interface.
type Jira struct{}

func (j *Jira) CreateIssue(title string, description string) error {
	// Simulação de criação de issue no Jira
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

func (j *Jira) UpdateIssue(issueID int, title string, description string) error {
	// Simulação de atualização do issue no Jira
	fmt.Printf("Updating issue %d: %s\n", issueID, title)
	return nil
}

// GoAgent implements the GoAgentClient interface.
type GoAgent struct{}

func (g *GoAgent) SendMetric(metricName string, value float64) error {
	// Simulação de envio de métrica para o Go Agent
	fmt.Printf("Sending metric %s: %f\n", metricName, value)
	return nil
}

// Main é a função principal que executa o programa.
func main() {
	jiraClient := &Jira{}
	goAgentClient := &GoAgent{}

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		log.Fatalf("Error creating issue: %v\n", err)
	}

	err = goAgentClient.SendMetric("go-agent.test", 10.5)
	if err != nil {
		log.Fatalf("Error sending metric: %v\n", err)
	}
}