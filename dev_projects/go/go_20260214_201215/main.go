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
	ScheduleJob(jobName string, cronExpression string) error
}

// JiraService implementa o JiraClient interface
type JiraService struct{}

func (js *JiraService) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira para criar um novo issue
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentService implementa o GoAgentClient interface
type GoAgentService struct{}

func (gas *GoAgentService) ScheduleJob(jobName string, cronExpression string) error {
	// Simulação de chamada à API do Go Agent para agendar um novo job
	fmt.Printf("Scheduling job: %s - Cron expression: %s\n", jobName, cronExpression)
	return nil
}

func main() {
	jiraClient := &JiraService{}
	goAgentClient := &GoAgentService{}

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		log.Fatalf("Error creating Jira issue: %v", err)
	}

	err = goAgentClient.ScheduleJob("Test Job", "* * * * ?")
	if err != nil {
		log.Fatalf("Error scheduling Go Agent job: %v", err)
	}
}