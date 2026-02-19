package main

import (
	"testing"
)

// JiraAPI é uma interface para a API do Jira
type JiraAPI interface {
	CreateIssue(title, description string) error
}

// GoAgentAPI é uma interface para o Go Agent
type GoAgentAPI interface {
	ScheduleJob(command string) error
}

// JiraClient implementa a interface JiraAPI
type JiraClient struct{}

func (jc *JiraClient) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentClient implementa a interface GoAgentAPI
type GoAgentClient struct{}

func (ga *GoAgentClient) ScheduleJob(command string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Scheduling job: %s\n", command)
	return nil
}

// JiraIntegration é uma função que integra Go Agent com Jira
func JiraIntegration() {
	jira := &JiraClient{}
	goAgent := &GoAgentClient{}

	// Criar um issue no Jira
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	// Enviar um comando para o Go Agent
	err = goAgent.ScheduleJob("Run tests")
	if err != nil {
		fmt.Println("Error scheduling job:", err)
		return
	}
}

func TestJiraIntegration(t *testing.T) {
	jira := &JiraClient{}
	goAgent := &GoAgentClient{}

	// Caso de sucesso com valores válidos
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Create issue failed: %v", err)
	}

	// Caso de erro (divisão por zero, valores inválidos, etc)
	err = jira.CreateIssue("", "")
	if err == nil {
		t.Errorf("Create issue should have failed with empty title and description")
	}
}