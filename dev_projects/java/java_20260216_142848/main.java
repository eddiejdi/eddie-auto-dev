package com.example.jiraagent;

import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.web.action.JiraWebActionSupport;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JiraAgent extends JiraWebActionSupport {

    @Autowired
    private Issue issue;

    public String doExecute() {
        try {
            // Simula uma atividade no sistema JIRA
            issue.setDescription("Atividade simulada pelo Java Agent");

            return SUCCESS;
        } catch (Exception e) {
            log.error("Erro ao executar o Java Agent", e);
            return ERROR;
        }
    }

    public Issue getIssue() {
        return issue;
    }

    public void setIssue(Issue issue) {
        this.issue = issue;
    }
}