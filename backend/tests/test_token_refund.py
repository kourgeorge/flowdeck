"""Test token refund functionality for failed executions."""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from database import SessionLocal
from models.db_models import User, Execution, TokenTransaction
from services import token_service


def test_refund_for_failed_execution():
    """Test that tokens are refunded when an execution fails."""
    db = SessionLocal()
    
    try:
        # Create a test user
        test_user = User(
            email=f"test_refund_{datetime.now().timestamp()}@test.com",
            name="Test User",
            token_balance=1000,
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        initial_balance = token_service.get_balance(test_user.id, db)
        print(f"Initial balance: {initial_balance}")
        
        # Deduct tokens for analysis
        success, execution_id = token_service.deduct_for_analysis(
            test_user.id, "AAPL", db
        )
        assert success, "Token deduction should succeed"
        assert execution_id is not None, "Execution ID should be returned"
        
        # Check balance after deduction
        balance_after_deduction = token_service.get_balance(test_user.id, db)
        print(f"Balance after deduction: {balance_after_deduction}")
        assert balance_after_deduction == initial_balance - token_service.COST_PER_ANALYSIS
        
        # Mark execution as failed
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        assert execution is not None, "Execution should exist"
        execution.status = "failed"
        execution.error_message = "Test failure"
        db.commit()
        
        # Refund tokens for failed execution
        refunded = token_service.refund_for_failed_execution(execution_id, db)
        assert refunded, "Refund should succeed"
        
        # Check balance after refund
        balance_after_refund = token_service.get_balance(test_user.id, db)
        print(f"Balance after refund: {balance_after_refund}")
        assert balance_after_refund == initial_balance, "Balance should be restored"
        
        # Verify refund transaction was created
        refund_tx = (
            db.query(TokenTransaction)
            .filter(
                TokenTransaction.related_entity_type == "execution",
                TokenTransaction.related_entity_id == execution_id,
                TokenTransaction.transaction_type == "refund",
            )
            .first()
        )
        assert refund_tx is not None, "Refund transaction should exist"
        assert refund_tx.amount == token_service.COST_PER_ANALYSIS, "Refund amount should match cost"
        print(f"Refund transaction: {refund_tx.description}")
        
        # Try to refund again - should fail (already refunded)
        refunded_again = token_service.refund_for_failed_execution(execution_id, db)
        assert not refunded_again, "Second refund should fail (already refunded)"
        
        # Balance should remain the same
        final_balance = token_service.get_balance(test_user.id, db)
        assert final_balance == initial_balance, "Balance should not change on duplicate refund"
        
        print("✓ All tests passed!")
        
    finally:
        # Cleanup
        if test_user.id:
            db.query(TokenTransaction).filter(
                TokenTransaction.user_id == test_user.id
            ).delete()
            db.query(Execution).filter(
                Execution.creator_id == test_user.id
            ).delete()
            db.query(User).filter(User.id == test_user.id).delete()
            db.commit()
        db.close()


def test_refund_only_for_failed_status():
    """Test that refund only works for executions with status='failed'."""
    db = SessionLocal()
    
    try:
        # Create a test user
        test_user = User(
            email=f"test_refund_status_{datetime.now().timestamp()}@test.com",
            name="Test User",
            token_balance=1000,
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Deduct tokens for analysis
        success, execution_id = token_service.deduct_for_analysis(
            test_user.id, "MSFT", db
        )
        assert success, "Token deduction should succeed"
        
        # Try to refund without marking as failed (status is 'running')
        refunded = token_service.refund_for_failed_execution(execution_id, db)
        assert not refunded, "Refund should fail for non-failed execution"
        
        # Mark as completed
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        execution.status = "completed"
        db.commit()
        
        # Try to refund completed execution
        refunded = token_service.refund_for_failed_execution(execution_id, db)
        assert not refunded, "Refund should fail for completed execution"
        
        print("✓ Status check tests passed!")
        
    finally:
        # Cleanup
        if test_user.id:
            db.query(TokenTransaction).filter(
                TokenTransaction.user_id == test_user.id
            ).delete()
            db.query(Execution).filter(
                Execution.creator_id == test_user.id
            ).delete()
            db.query(User).filter(User.id == test_user.id).delete()
            db.commit()
        db.close()


if __name__ == "__main__":
    print("Testing token refund functionality...\n")
    test_refund_for_failed_execution()
    print()
    test_refund_only_for_failed_status()
    print("\n✓ All token refund tests passed!")

# Made with Bob
