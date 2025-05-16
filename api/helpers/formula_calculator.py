from simpleeval import simple_eval, NumberTooHigh, InvalidExpression, FunctionNotDefined

def calculate_price_with_formula(formula: str, base_price: float) -> float | None:
    """
    Calculates a price based on a formula string and a base price.

    Args:
        formula: The formula string to evaluate.
                 The formula can use the variable 'price' which will be the base_price.
        base_price: The base price (e.g., price_eur_kwh) to use in the formula.

    Returns:
        The calculated price as a float, or None if evaluation fails or the formula is invalid.
    """
    try:
        # The variable name 'price' in the formula will be substituted with base_price
        return simple_eval(
            formula,
            names={"price": base_price}
        )
    except (NumberTooHigh, InvalidExpression, FunctionNotDefined) as e:
        # Log the error or handle it as needed
        print(f"Error evaluating formula '{formula}' with base_price {base_price}: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during evaluation
        print(f"Unexpected error evaluating formula '{formula}' with base_price {base_price}: {e}")
        return None
