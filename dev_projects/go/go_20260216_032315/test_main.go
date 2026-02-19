package main

import (
	"testing"
)

// Teste para criar uma nova tarefa no Jira
func TestCreateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("Tarefa de exemplo", "Descrição da tarefa")
	if err != nil {
		t.Errorf("Erro ao criar tarefa: %v", err)
	}
}

// Teste para atualizar uma tarefa existente no Jira
func TestUpdateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.UpdateIssue(1, "Tarefa atualizada", "Nova descrição da tarefa")
	if err != nil {
		t.Errorf("Erro ao atualizar tarefa: %v", err)
	}
}

// Teste para monitorar o progresso de um processo
func TestMonitorProcesso(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.MonitorProcesso()
	if err != nil {
		t.Errorf("Erro ao monitorar o processo: %v", err)
	}
}