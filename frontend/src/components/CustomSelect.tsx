import { useState, useEffect } from 'react';

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

export interface SelectOptionGroup {
  group: string;
  options: SelectOption[];
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options?: SelectOption[];
  groupedOptions?: SelectOptionGroup[];
  placeholder?: string;
  className?: string;
}

export default function CustomSelect({
  value,
  onChange,
  options,
  groupedOptions,
  placeholder = 'Select an option',
  className = '',
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Flatten grouped options if provided
  const allOptions = groupedOptions
    ? groupedOptions.flatMap((g) => g.options)
    : options || [];

  const selected = allOptions.find((opt) => opt.value === value);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-custom-select-root="true"]')) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const renderOptions = () => {
    if (groupedOptions) {
      return groupedOptions.map((group) => (
        <div key={group.group}>
          {group.group && (
            <div className="sticky top-0 border-b border-gray-800 bg-gray-950 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {group.group}
              </p>
            </div>
          )}
          <div className="p-1">
            {group.options.map((option) => renderOption(option))}
          </div>
        </div>
      ));
    }

    return <div className="p-1">{allOptions.map((option) => renderOption(option))}</div>;
  };

  const renderOption = (option: SelectOption) => {
    const isSelected = option.value === value;
    return (
      <button
        key={option.value}
        type="button"
        onClick={() => {
          onChange(option.value);
          setIsOpen(false);
        }}
        className={`flex w-full items-start gap-3 rounded-md px-3 py-2 text-left transition-colors ${
          isSelected
            ? 'bg-blue-600 text-white'
            : 'text-gray-200 hover:bg-gray-800'
        }`}
        role="option"
        aria-selected={isSelected}
      >
        {isSelected && (
          <svg className="mt-0.5 h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        )}
        <div className={`min-w-0 flex-1 ${!isSelected && option.description ? 'ml-7' : ''}`}>
          <p className={`text-sm ${isSelected ? 'font-semibold' : 'font-medium'}`}>
            {option.label}
          </p>
          {option.description && (
            <p className={`mt-0.5 text-xs ${isSelected ? 'text-blue-100' : 'text-gray-400'}`}>
              {option.description}
            </p>
          )}
        </div>
      </button>
    );
  };

  return (
    <div className={`relative ${className}`} data-custom-select-root="true">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full rounded-lg border px-3 py-2.5 text-left transition-all ${
          isOpen
            ? 'border-blue-500 bg-gray-800 ring-2 ring-blue-500/50'
            : 'border-gray-700 bg-gray-800 hover:border-gray-600'
        }`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <p className={`text-sm font-medium ${selected ? 'text-white' : 'text-gray-400'}`}>
              {selected ? selected.label : placeholder}
            </p>
            {selected?.description && (
              <p className="mt-0.5 text-xs text-gray-400">{selected.description}</p>
            )}
          </div>
          <svg
            className={`ml-2 h-4 w-4 flex-shrink-0 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 max-h-80 overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-2xl">
          <div className="max-h-80 overflow-y-auto">{renderOptions()}</div>
        </div>
      )}
    </div>
  );
}

// Made with Bob
